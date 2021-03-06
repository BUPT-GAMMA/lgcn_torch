import argparse

from utils.train_utils import add_flags_from_config

config_args = {
    'training_config': {
        'lr': (0.005, 'learning rate'),
        'dropout': (0.5, 'dropout probability'),
        'cuda': (0, 'which cuda device to use (-1 for cpu training)'),
        'epochs': (3000, 'maximum number of epochs to train for'),
        'weight-decay': (0.0001, 'l2 regularization strength'),
        'optimizer': ('Adam', 'which optimizer to use, can be any of [Adam, RiemannianAdam]'),
        'momentum': (0.999, 'momentum in optimizer'),
        'patience': (200, 'patience for early stopping'),
        'seed': (1, 'seed for training'),
        'log-freq': (5, 'how often to compute print train/val metrics (in epochs)'),
        'eval-freq': (1, 'how often to compute val metrics (in epochs)'),
        'save': (0, '1 to save model and logs and 0 otherwise'),
        'save-dir': (None, 'path to save training logs and model weights (defaults to logs/task/date/run/)'),
        'sweep-c': (0, ''),
        'lr-reduce-freq': (None, 'reduce lr every lr-reduce-freq or None to keep lr constant'),
        'gamma': (0.5, 'gamma for lr scheduler'),
        'print-epoch': (True, ''),
        'grad-clip': (None, 'max norm for gradient clipping, or None for no gradient clipping'),
        'min-epochs': (100, 'do not early stop before min-epochs')
    },
    'model_config': {
        'run_times': (1, 'number of running times'),
        'task': ('nc', 'which tasks to train on, can be any of [lp, nc]'),
        'model': ('LGCN', 'which encoder to use, can be any of [Shallow, LGCN]'),
        'dim': (64, 'embedding dimension'),
        'manifold': ('Lorentzian', 'which manifold to use, can be any of [Euclidean, Lorentzian]'),
        'c': (1, 'curvature, set to None for trainable curvature'),
        'r': (2., 'fermi-dirac decoder parameter for lp'),
        't': (1., 'fermi-dirac decoder parameter for lp'),
        'pretrained-embeddings': (None, 'path to pretrained embeddings (.npy file) for Shallow node classification'),
        'pos-weight': (0, 'whether to upweight positive class in node classification tasks'),
        'num-layers': (2, 'number of hidden layers in encoder'),
        'bias': (1, 'whether to use bias (1) or not (0)'),
        'act': ('elu', 'which activation function to use (or None for no activation)'),
        'n-heads': (1, 'number of attention heads for graph attention networks, must be a divisor dim'),
        'alpha': (0.2, 'alpha for leakyrelu in graph attention networks'),
        'use-att': (1, 'whether to use hyperbolic attention in HyperGCN model'),
        'double-precision': ('0', 'whether to use double precision')
    },
    'data_config': {
        'dataset': ('cora', 'which dataset to use'),
        'val-prop': (0.05, 'proportion of validation edges for link prediction'), # origin 0.05
        'test-prop': (0.1, 'proportion of test edges for link prediction'), # origin 0.1
        'use-feats': (1, 'whether to use node features or not'),
        'normalize-feats': (1, 'whether to normalize input node features'),
        'normalize-adj': (1, 'whether to row-normalize the adjacency matrix. 0 for no-normalize, 1 for row-normalize, 2 for all normalize'),
        'split-seed': (1234, 'seed for data splits (train/test/val)'),
    }
}

parser = argparse.ArgumentParser()
for _, config_dict in config_args.items():
    parser = add_flags_from_config(parser, config_dict)
