"""Data utils functions for pre-processing and data loading."""
import os
import pickle as pkl
import sys

import networkx as nx
import numpy as np
import scipy.sparse as sp
import torch

def load_data(args, datapath):
    if args.task == 'nc':
        data = load_data_nc(args.dataset, args.use_feats, datapath, args.split_seed)
    else:
        data = load_data_lp(args.dataset, args.use_feats, datapath)
        adj = data['adj_train']
        if args.task == 'lp':
            print('start to mask edges')
            adj_train, train_edges, train_edges_false, val_edges, val_edges_false, test_edges, test_edges_false = mask_edges(
                    adj, args.val_prop, args.test_prop, args.split_seed
            )
            data['adj_train'] = adj_train
            data['train_edges'], data['train_edges_false'] = train_edges, train_edges_false
            data['val_edges'], data['val_edges_false'] = val_edges, val_edges_false
            data['test_edges'], data['test_edges_false'] = test_edges, test_edges_false
    data['adj_train_norm'], data['features'] = process(
            data['adj_train'], data['features'], args.normalize_adj, args.normalize_feats
    )
    return data


# ############### FEATURES PROCESSING ####################################


def process(adj, features, normalize_adj, normalize_feats):
    if sp.isspmatrix(features):
        features = np.array(features.todense())
    if normalize_feats:
        features = normalize(features)
    features = torch.Tensor(features)
    if normalize_adj == 1:
        adj = normalize(adj + sp.eye(adj.shape[0]))
    elif normalize_adj == 2:
        adj = adj + sp.eye(adj.shape[0])
        adj = sym_normalize_adj(adj)
    adj = sparse_mx_to_torch_sparse_tensor(adj)
    return adj, features


def sym_normalize_adj(adj):
    """used in GCN Symmetrically normalize adjacency matrix."""
    adj = sp.coo_matrix(adj)
    rowsum = np.array(adj.sum(1))
    d_inv_sqrt = np.power(rowsum, -0.5).flatten()
    d_inv_sqrt[np.isinf(d_inv_sqrt)] = 0.
    d_mat_inv_sqrt = sp.diags(d_inv_sqrt)
    return adj.dot(d_mat_inv_sqrt).transpose().dot(d_mat_inv_sqrt).tocoo()

def normalize(mx):
    """Row-normalize sparse matrix."""
    rowsum = np.array(mx.sum(1))
    r_inv = np.power(rowsum, -1).flatten()
    r_inv[np.isinf(r_inv)] = 0.
    r_mat_inv = sp.diags(r_inv)
    mx = r_mat_inv.dot(mx)
    return mx


def sparse_mx_to_torch_sparse_tensor(sparse_mx):
    """Convert a scipy sparse matrix to a torch sparse tensor."""
    sparse_mx = sparse_mx.tocoo()
    indices = torch.from_numpy(
            np.vstack((sparse_mx.row, sparse_mx.col)).astype(np.int64)
    )
    values = torch.Tensor(sparse_mx.data)
    shape = torch.Size(sparse_mx.shape)
    return torch.sparse.FloatTensor(indices, values, shape)


# ############### DATA SPLITS #####################################################


def mask_edges(adj, val_prop, test_prop, seed):
    np.random.seed(seed)  # get tp edges
    x, y = sp.triu(adj).nonzero()
    pos_edges = np.array(list(zip(x, y)))
    np.random.shuffle(pos_edges)
    # get tn edges
    x, y = sp.triu(sp.csr_matrix(1. - adj.toarray())).nonzero()
    neg_edges = np.array(list(zip(x, y)))
    np.random.shuffle(neg_edges)

    m_pos = len(pos_edges)
    n_val = int(m_pos * val_prop)
    n_test = int(m_pos * test_prop)
    val_edges, test_edges, train_edges = pos_edges[:n_val], pos_edges[n_val:n_test + n_val], pos_edges[n_test + n_val:]
    val_edges_false, test_edges_false = neg_edges[:n_val], neg_edges[n_val:n_test + n_val]
    train_edges_false = np.concatenate([neg_edges, val_edges, test_edges], axis=0)  # ??? is the can not link in train?
    adj_train = sp.csr_matrix((np.ones(train_edges.shape[0]), (train_edges[:, 0], train_edges[:, 1])), shape=adj.shape)
    adj_train = adj_train + adj_train.T
    return adj_train, torch.LongTensor(train_edges), torch.LongTensor(train_edges_false), torch.LongTensor(val_edges), \
           torch.LongTensor(val_edges_false), torch.LongTensor(test_edges), torch.LongTensor(
            test_edges_false)  


def split_data(labels, val_prop, test_prop, seed):
    np.random.seed(seed)
    nb_nodes = labels.shape[0]
    all_idx = np.arange(nb_nodes)
    pos_idx = labels.nonzero()[0]
    neg_idx = (1. - labels).nonzero()[0]
    np.random.shuffle(pos_idx)
    np.random.shuffle(neg_idx)
    pos_idx = pos_idx.tolist()
    neg_idx = neg_idx.tolist()
    nb_pos_neg = min(len(pos_idx), len(neg_idx))
    nb_val = round(val_prop * nb_pos_neg)
    nb_test = round(test_prop * nb_pos_neg)
    idx_val_pos, idx_test_pos, idx_train_pos = pos_idx[:nb_val], pos_idx[nb_val:nb_val + nb_test], pos_idx[
                                                                                                   nb_val + nb_test:]
    idx_val_neg, idx_test_neg, idx_train_neg = neg_idx[:nb_val], neg_idx[nb_val:nb_val + nb_test], neg_idx[
                                                                                                   nb_val + nb_test:]
    return idx_val_pos + idx_val_neg, idx_test_pos + idx_test_neg, idx_train_pos + idx_train_neg


# ############### LINK PREDICTION DATA LOADERS ####################################


def load_data_lp(dataset, use_feats, data_path):
    if dataset in ['cora', 'pubmed', 'citeseer', 'amazon']:
        adj, features = load_citation_data(dataset, use_feats, data_path)[:2]
    elif dataset == 'disease_lp':
        adj, features = load_synthetic_data(dataset, use_feats, data_path)[:2]
    elif dataset == 'usa':
        adj, features, _,_, _, _ = load_other(dataset, use_feats, data_path)
    else:
        raise FileNotFoundError('Dataset {} is not supported.'.format(dataset))
    data = {'adj_train': adj, 'features': features}
    return data


# ############### NODE CLASSIFICATION DATA LOADERS ####################################


def load_data_nc(dataset, use_feats, data_path, split_seed):
    if dataset in ['pubmed','cora','citeseer']:
        adj, features, labels, idx_train, idx_val, idx_test = load_citation_data(
            dataset, use_feats, data_path, split_seed
        )
    elif dataset[:3] == 'amazon':
        adj, features, labels, idx_train, idx_val, idx_test = load_citation_data(
            dataset, use_feats, data_path, split_seed
        )
    elif dataset == 'airport':
        adj, features, labels, idx_val, idx_test, idx_train = load_other(dataset, use_feats, data_path)
    else:
        if dataset == 'disease_nc':
            val_prop, test_prop = 0.10, 0.60
            adj, features, labels = load_synthetic_data(dataset, use_feats, data_path)
        else:
            raise FileNotFoundError('Dataset {} is not supported.'.format(dataset))
        idx_val, idx_test, idx_train = split_data(labels, val_prop, test_prop, seed=split_seed)

    labels = torch.LongTensor(labels)
    data = {'adj_train': adj, 'features': features, 'labels': labels, 'idx_train': idx_train, 'idx_val': idx_val,
            'idx_test': idx_test}
    return data


# ############### DATASETS ####################################
def sample_mask(idx, l):
    """Create mask."""
    mask = np.zeros(l)
    mask[idx] = 1
    return np.array(mask, dtype=np.bool)

def load_citation_data(dataset_str, use_feats, data_path, split_seed=None):
    if dataset_str[:3] == 'my_':
        names1 = ['adj_matrix.npz', 'attr_matrix.npz']
        names2 = ['label_matrix.npy', 'train_mask.npy', 'val_mask.npy', 'test_mask.npy']
        objects = []
        for tmp_name in names1:
            tmp_path = 'data/{}/{}.{}'.format(dataset_str, dataset_str, tmp_name)
            objects.append(sp.load_npz(tmp_path))
        for tmp_name in names2:
            tmp_path = 'data/{}/{}.{}'.format(dataset_str, dataset_str, tmp_name)
            objects.append(np.load(tmp_path))
        adj, features, label_matrix, train_mask, val_mask, test_mask = tuple(objects)

        labels = np.argmax(label_matrix, 1)

        arr = np.arange(len(train_mask))
        idx_train = list(arr[train_mask])
        idx_val = list(arr[val_mask])
        idx_test = list(arr[test_mask])
        return adj, features, labels, idx_train, idx_val, idx_test
        
    names = ['x', 'y', 'tx', 'ty', 'allx', 'ally', 'graph']
    objects = []
    for i in range(len(names)):
        with open(os.path.join(data_path, "ind.{}.{}".format(dataset_str, names[i])), 'rb') as f:
            if sys.version_info > (3, 0):
                objects.append(pkl.load(f, encoding='latin1'))
            else:
                objects.append(pkl.load(f))

    x, y, tx, ty, allx, ally, graph = tuple(objects)
    test_idx_reorder = parse_index_file(os.path.join(data_path, "ind.{}.test.index".format(dataset_str)))
    test_idx_range = np.sort(test_idx_reorder)

    if dataset_str == 'citeseer':
        # Fix citeseer dataset (there are some isolated nodes in the graph)
        # Find isolated nodes, add them as zero-vecs into the right position
        test_idx_range_full = range(min(test_idx_reorder), max(test_idx_reorder)+1)
        tx_extended = sp.lil_matrix((len(test_idx_range_full), x.shape[1]))
        tx_extended[test_idx_range-min(test_idx_range), :] = tx
        tx = tx_extended
        ty_extended = np.zeros((len(test_idx_range_full), y.shape[1]))
        ty_extended[test_idx_range-min(test_idx_range), :] = ty
        ty = ty_extended

    features = sp.vstack((allx, tx)).tolil()
    features[test_idx_reorder, :] = features[test_idx_range, :]

    labels = np.vstack((ally, ty))
    labels[test_idx_reorder, :] = labels[test_idx_range, :]
    labels = np.argmax(labels, 1)

    idx_test = test_idx_range.tolist()
    idx_train = list(range(len(y)))
    idx_val = range(len(y), len(y) + 500)

    adj = nx.adjacency_matrix(nx.from_dict_of_lists(graph))
    if not use_feats:
        features = sp.eye(adj.shape[0])
    return adj, features, labels, idx_train, idx_val, idx_test


def parse_index_file(filename):
    index = []
    for line in open(filename):
        index.append(int(line.strip()))
    return index


def load_synthetic_data(dataset_str, use_feats, data_path):
    object_to_idx = {}
    idx_counter = 0
    edges = []
    with open(os.path.join(data_path, "{}.edges.csv".format(dataset_str)), 'r') as f:
        all_edges = f.readlines()
    for line in all_edges:
        n1, n2 = line.rstrip().split(',')
        if n1 in object_to_idx:
            i = object_to_idx[n1]
        else:
            i = idx_counter
            object_to_idx[n1] = i
            idx_counter += 1
        if n2 in object_to_idx:
            j = object_to_idx[n2]
        else:
            j = idx_counter
            object_to_idx[n2] = j
            idx_counter += 1
        edges.append((i, j))
    adj = np.zeros((len(object_to_idx), len(object_to_idx)))
    for i, j in edges:
        adj[i, j] = 1.  # comment this line for directed adjacency matrix
        adj[j, i] = 1.
    if use_feats:
        features = sp.load_npz(os.path.join(data_path, "{}.feats.npz".format(dataset_str)))
    else:
        features = sp.eye(adj.shape[0])
    labels = np.load(os.path.join(data_path, "{}.labels.npy".format(dataset_str)))
    return sp.csr_matrix(adj), features, labels


def load_other(dataset_str, use_feats, data_path):
    adj = sp.load_npz(os.path.join(data_path, "{}.adj.npz".format(dataset_str)))
    if dataset_str == 'airport':
        features = sp.eye(adj.get_shape()[0])
    else:
        if use_feats:
            features = sp.load_npz(os.path.join(data_path, "{}.feats.npz".format(dataset_str)))
        else:
            features = sp.eye(adj.get_shape()[0])
    labels = np.load(os.path.join(data_path, "{}.labels.npy".format(dataset_str)))
    idx_val = np.load(os.path.join(data_path, "{}.val.npy".format(dataset_str))).tolist()
    idx_test = np.load(os.path.join(data_path, "{}.test.npy".format(dataset_str))).tolist()
    idx_train = np.load(os.path.join(data_path, "{}.train.npy".format(dataset_str))).tolist()
    return adj, features, labels, idx_val, idx_test, idx_train
