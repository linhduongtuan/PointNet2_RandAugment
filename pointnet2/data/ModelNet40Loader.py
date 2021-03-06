from __future__ import (
    division,
    absolute_import,
    with_statement,
    print_function,
    unicode_literals,
)
import torch
import torch.utils.data as data
import numpy as np
import os
import h5py
import subprocess
import shlex

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _get_data_files(list_filename):
    with open(list_filename) as f:
        return [line.rstrip()[5:] for line in f]


def _load_data_file(name):
    f = h5py.File(name)
    data = f["data"][:]
    label = f["label"][:]
    return data, label


def FarthestPointSample(point, npoint):
    """
    Input:
        xyz: pointcloud data, [N, D]
        npoint: number of samples
    Return:
        centroids: sampled pointcloud index, [npoint, D]
    References : https://github.com/yanx27/Pointnet_Pointnet2_pytorch/blob/master/data_utils/ModelNetDataLoader.py
    """
    N, D = point.shape
    xyz = point[:,:3]
    centroids = np.zeros((npoint,))
    distance = np.ones((N,)) * 1e10
    farthest = np.random.randint(0, N)
    for i in range(npoint):
        centroids[i] = farthest
        centroid = xyz[farthest, :]
        dist = np.sum((xyz - centroid) ** 2, -1)
        mask = dist < distance
        distance[mask] = dist[mask]
        farthest = np.argmax(distance, -1)
    point = point[centroids.astype(np.int32)]
    return point

class ModelNet40Cls(data.Dataset):
    def __init__(self, num_points, transforms=None, train=True, download=True):
        super().__init__()

        self.transforms = transforms

        self.folder = "modelnet40_ply_hdf5_2048"
        self.data_dir = os.path.join(BASE_DIR, self.folder)
        self.url = "https://shapenet.cs.stanford.edu/media/modelnet40_ply_hdf5_2048.zip"

        if download and not os.path.exists(self.data_dir):
            zipfile = os.path.join(BASE_DIR, os.path.basename(self.url))
            subprocess.check_call(
                shlex.split("curl {} -o {}".format(self.url, zipfile))
            )

            subprocess.check_call(
                shlex.split("unzip {} -d {}".format(zipfile, BASE_DIR))
            )

            subprocess.check_call(shlex.split("rm {}".format(zipfile)))

        self.train = train
        if self.train:
            self.files = _get_data_files(os.path.join(self.data_dir, "train_files.txt"))
        else:
            self.files = _get_data_files(os.path.join(self.data_dir, "test_files.txt"))

        point_list, label_list = [], []
        for f in self.files:
            points, labels = _load_data_file(os.path.join(BASE_DIR, f))
            point_list.append(points)
            label_list.append(labels)

        self.points = np.concatenate(point_list, 0)
        self.labels = np.concatenate(label_list, 0)
        self.set_num_points(num_points)

    def __getitem__(self, idx):
        # pt_idxs = np.arange(0, self.num_points)
        # np.random.shuffle(pt_idxs)
        # sampled_points = self.points[idx, pt_idxs].copy()

        points = self.points[idx].copy()
        sampled_points = FarthestPointSample(point= points, npoint=self.num_points)
        label = torch.from_numpy(self.labels[idx]).type(torch.LongTensor)

        if self.transforms is not None:
            sampled_points = self.transforms(sampled_points)

        return sampled_points, label

    def __len__(self):
        return self.points.shape[0]

    def set_num_points(self, pts):
        self.num_points = min(self.points.shape[1], pts)

    def randomize(self):
        pass


if __name__ == "__main__":
    from torchvision import transforms
    import data_utils as d_utils
    import open3d as o3d
    from RandAugment import RandAugment
    import argparse

    def parse_args():
        parser = argparse.ArgumentParser(
            description = "Arguments for ModelNet Visualization",
            formatter_class = argparse.ArgumentDefaultsHelpFormatter,
        )
        parser.add_argument("-N", type=int, default=4, help="RandAugment N")
        parser.add_argument("-M", type=int, default=4, help="RandAugment M")

        return parser.parse_args()

    args = parse_args()
    transforms = transforms.Compose(
        [
            RandAugment(n=args.N, m=args.M),
            d_utils.PointCloudToTensor(),
            d_utils.PointCloudNormalize(),
        ]
    )

    dset = ModelNet40Cls(1024, train = True, transforms=transforms)
    pc , _ = dset[100]
    pc = pc[:,0:3]
    #dloader = torch.utils.data.DataLoader(dset, batch_size = 1, shuffle=True)

    xyz = pc.numpy()
    # Pass xyz to Open3D.o3d.geometry.PointCloud and visualize
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(xyz)
    o3d.io.write_point_cloud("sync.ply", pcd)

    # Load saved point cloud and visualize it
    pcd_load = o3d.io.read_point_cloud("sync.ply")
    o3d.visualization.draw_geometries([pcd_load])

    # convert Open3D.o3d.geometry.PointCloud to numpy array
    xyz_load = np.asarray(pcd_load.points)
    print('xyz_load')
    print(xyz_load)
