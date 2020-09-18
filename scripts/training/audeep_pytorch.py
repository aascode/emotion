import argparse
import time
from pathlib import Path
from typing import Union

import netCDF4
import numpy as np
import torch
from tqdm import tqdm
from torch import nn
from torch.nn import functional as F
from torch.utils.data import TensorDataset, DataLoader
from torch.utils.tensorboard import SummaryWriter

from emotion_recognition.dataset import write_netcdf_dataset

# Workaround for having both PyTorch and TensorFlow installed.
import tensorflow as tf
import tensorboard as tb
tf.io.gfile = tb.compat.tensorflow_stub.io.gfile

DEVICE = torch.device('cuda:0')


class TimeRecurrentAutoencoder(nn.Module):
    def __init__(self, n_features: int,
                 n_units: int = 256,
                 n_layers: int = 2,
                 dropout: float = 0.2,
                 bidirectional_encoder: bool = False,
                 bidirectional_decoder: bool = False):
        super().__init__()

        encoder_state_size = n_units * n_layers
        decoder_state_size = n_units * n_layers
        if bidirectional_encoder:
            encoder_state_size *= 2
        if bidirectional_decoder:
            decoder_state_size *= 2
        decoder_output_size = n_units * n_layers  # concat(fwd, back)

        self.n_features = n_features
        self.n_units = n_units
        self.n_layers = n_layers
        self.dropout = dropout
        self.bidirectional_encoder = bidirectional_encoder
        self.bidirectional_decoder = bidirectional_decoder

        self.encoder = nn.GRU(
            n_features, n_units, num_layers=n_layers, dropout=dropout,
            bidirectional=bidirectional_encoder, batch_first=True
        )
        self.representation = nn.Sequential(
            nn.Linear(encoder_state_size, decoder_state_size),
            nn.Tanh()
        )
        self.decoder = nn.GRU(
            n_features, n_units, num_layers=n_layers, dropout=dropout,
            bidirectional=bidirectional_decoder, batch_first=True
        )
        self.reconstruction = nn.Sequential(
            nn.Linear(decoder_output_size, n_features), nn.Tanh())

    def forward(self, x: torch.Tensor):
        targets = x.flip(1)

        num_directions = 2 if self.bidirectional_encoder else 1
        encoder_h = torch.zeros(self.n_layers * num_directions, x.size(0),
                                self.n_units, device=x.device)
        _, encoder_h = self.encoder(
            F.dropout(x, self.dropout, self.training), encoder_h)
        encoder_h = torch.cat(encoder_h.unbind(), -1)

        representation = self.representation(encoder_h)

        num_directions = 2 if self.bidirectional_decoder else 1
        decoder_h = torch.stack(representation.chunk(
            self.n_layers * num_directions, -1))

        decoder_input = F.pad(targets[:, :-1, :], [0, 0, 1, 0])
        decoder_seq, _ = self.decoder(
            F.dropout(decoder_input, self.dropout, self.training), decoder_h)
        decoder_seq = F.dropout(decoder_seq, self.dropout, self.training)

        reconstruction = self.reconstruction(decoder_seq)
        reconstruction = reconstruction.flip(1)
        return reconstruction, representation


def rmse_loss(x: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """Root-mean-square error loss function."""
    return torch.sqrt(torch.mean((x - y)**2))


def get_latest_save(directory: Union[str, Path]) -> Path:
    """Gets the path to the latest model checkpoint, assuming it was saved with
    the format 'model-XXXX.pt'

    Args:
    -----
    directory: Path or str
        The path to a directory containing the model save files.

    Returns:
        The path to the latest model save file (i.e. the one with the highest
        epoch number).
    """
    directory = Path(directory)
    saves = list(directory.glob('model-*.pt'))
    if len(saves) == 0:
        raise FileNotFoundError(
            "No save files found in directory {}".format(directory))
    return max(saves, key=lambda p: int(p.stem.split('-')[1]))


def train(args):
    print("Reading input from {}.".format(args.input))
    dataset = netCDF4.Dataset(args.input)
    x = np.array(dataset.variables['features'])
    dataset.close()
    np.random.default_rng().shuffle(x)

    x = torch.tensor(x)

    n_valid = int(args.valid_fraction * x.size(0))
    train_data = TensorDataset(x[n_valid:])
    valid_data = TensorDataset(x[:n_valid])
    train_dl = DataLoader(train_data, batch_size=args.batch_size, shuffle=True,
                          pin_memory=True)
    valid_dl = DataLoader(valid_data, batch_size=args.batch_size,
                          pin_memory=True)

    if args.cont:
        save_path = get_latest_save(args.logs)
        load_dict = torch.load(save_path)
        model_args = load_dict['model_args']
        optimiser_args = load_dict['optimiser_args']
        initial_epoch = 1 + load_dict['epoch']
    else:
        model_args = dict(
            n_features=x.size(2), n_units=args.units, n_layers=args.layers,
            dropout=args.dropout,
            bidirectional_encoder=args.bidirectional_encoder,
            bidirectional_decoder=args.bidirectional_decoder
        )
        optimiser_args = dict(lr=args.learning_rate, eps=1e-5)
        initial_epoch = 1

    model = TimeRecurrentAutoencoder(**model_args)
    model = model.cuda(DEVICE)
    optimiser = torch.optim.Adam(model.parameters(), **optimiser_args)

    if args.cont:
        print("Restoring model from {}".format(save_path))
        model.load_state_dict(load_dict['model_state_dict'])
        optimiser.load_state_dict(load_dict['optimiser_state_dict'])

    args.logs.mkdir(parents=True, exist_ok=True)
    train_writer = SummaryWriter(args.logs / 'train')
    valid_writer = SummaryWriter(args.logs / 'valid')
    with torch.no_grad():
        batch = next(iter(train_dl))[0].to(DEVICE)
        train_writer.add_graph(model, input_to_model=batch)

    loss_fn = rmse_loss
    for epoch in range(initial_epoch, initial_epoch + args.epochs):
        start_time = time.perf_counter()
        model.train()
        train_losses = []
        for x, in tqdm(train_dl):
            x = x.to(DEVICE)
            optimiser.zero_grad()
            reconstruction, representation = model(x)

            loss = loss_fn(x, reconstruction)
            train_losses.append(loss.item())

            loss.backward()
            # Clip gradients to [-2, 2]
            nn.utils.clip_grad_value_(model.parameters(), 2)
            optimiser.step()
        train_time = time.perf_counter() - start_time
        train_loss = np.mean(train_losses)

        model.eval()
        with torch.no_grad():
            valid_losses = []
            it = iter(valid_dl)

            # Get loss and write summaries for first batch
            x = next(it)[0].to(DEVICE)
            reconstruction, representation = model(x)
            loss = loss_fn(x, reconstruction)
            valid_losses.append(loss.item())

            images = torch.cat([x, reconstruction], 2).unsqueeze(-1)
            images = (images + 1) / 2
            images = images[:20]
            valid_writer.add_images('reconstruction', images,
                                    global_step=epoch, dataformats='NHWC')
            valid_writer.add_histogram('representation', representation,
                                       global_step=epoch)

            # Just get the loss for the rest, no summaries
            for x, in it:
                x = x.to(DEVICE)
                reconstruction, representation = model(x)
                loss = loss_fn(x, reconstruction)
                valid_losses.append(loss.item())
            valid_loss = np.mean(valid_losses)

            train_writer.add_scalar('loss', train_loss, global_step=epoch)
            valid_writer.add_scalar('loss', valid_loss, global_step=epoch)

            end_time = time.perf_counter() - start_time

            print(
                "Epoch {:03d} in {:.2f}s ({:.2f}s per batch), train loss: "
                "{:.4f}, valid loss: {:.4f}".format(
                    epoch, end_time, train_time / len(train_dl), train_loss,
                    valid_loss
                )
            )

    save_path = args.logs / 'model-{:04d}.pt'.format(epoch)
    torch.save(
        {
            'epoch': epoch,
            'model_state_dict': model.state_dict(),
            'model_args': model_args,
            'optimiser_state_dict': optimiser.state_dict(),
            'optimiser_args': optimiser_args
        },
        save_path
    )
    print("Saved model to {}.".format(save_path))


def generate(args):
    if args.model.is_dir():
        save_path = get_latest_save(args.model)
    else:
        save_path = args.model
    print("Restoring model from {}.".format(save_path))
    load_dict = torch.load(save_path)
    model = TimeRecurrentAutoencoder(**load_dict['model_args'])
    model.cuda()
    model.load_state_dict(load_dict['model_state_dict'])

    dataset = netCDF4.Dataset(args.input)
    x = np.array(dataset.variables['features'])
    filenames = np.array(dataset.variables['filename'])
    labels = np.array(dataset.variables['label_nominal'])
    corpus = dataset.corpus
    dataset.close()

    representations = []
    with torch.no_grad():
        model.eval()
        for i in range(0, len(x), args.batch_size):
            batch = torch.tensor(x[i:i + args.batch_size], device=DEVICE)
            _, representation = model(batch)
            representations.append(representation.cpu().numpy())
    representations = np.concatenate(representations)

    valid_writer = SummaryWriter(save_path.parent / 'embedding')
    valid_writer.add_embedding(
        representations, list(zip(filenames, labels)),  tag=corpus,
        global_step=load_dict['epoch'], metadata_header=['filenames', 'labels']
    )

    annotation_path = Path('datasets') / corpus / 'labels.csv'
    write_netcdf_dataset(
        args.output, corpus=corpus, names=filenames,
        features=representations, slices=np.arange(len(filenames)),
        annotation_path=annotation_path, annotation_type='classification'
    )
    print("Wrote netCDF4 file to {}.".format(args.output))


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(title='command', dest='command',
                                       required=True)

    # Training arguments
    train_args = subparsers.add_parser('train')
    train_args.add_argument('--input', type=Path, required=True)
    train_args.add_argument('--logs', type=Path, required=True)

    train_args.add_argument('--units', type=int, default=256)
    train_args.add_argument('--layers', type=int, default=2)
    train_args.add_argument('--dropout', type=float, default=0.2)
    train_args.add_argument('--bidirectional_encoder', action='store_true')
    train_args.add_argument('--bidirectional_decoder', action='store_true')

    train_args.add_argument('--batch_size', type=int, default=64)
    train_args.add_argument('--epochs', type=int, default=50)
    train_args.add_argument('--learning_rate', type=float, default=0.001)
    train_args.add_argument('--valid_fraction', type=float, default=0.2)
    train_args.add_argument('--continue', dest='cont', action='store_true')

    # Feature generation arguments
    gen_args = subparsers.add_parser('generate')
    gen_args.add_argument('--input', type=Path, required=True)
    gen_args.add_argument('--model', type=Path, required=True)
    gen_args.add_argument('--output', type=Path, required=True)

    gen_args.add_argument('--batch_size', type=int, default=128)

    args = parser.parse_args()

    if args.command == 'train':
        train(args)
    elif args.command == 'generate':
        generate(args)


if __name__ == "__main__":
    main()
