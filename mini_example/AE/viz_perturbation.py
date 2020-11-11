#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Nov 11 21:38:43 2018

@author: zhao
"""

import argparse
import sys
import os
import numpy as np
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.nn.functional as F
from torch.autograd import Variable
from torchvision import datasets, transforms
import torch.optim as optim

from collections import OrderedDict
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, '../../models')))
sys.path.append(os.path.abspath(os.path.join(BASE_DIR, '../../dataloaders')))
import shapenet_part_loader


from pointcapsnet_ae import PointCapsNet
from open3d import *
import matplotlib.pyplot as plt


USE_CUDA = True
parser = argparse.ArgumentParser()
parser.add_argument('--batch_size', type=int, default=8, help='input batch size')
parser.add_argument('--num_points', type=int, default=2048, help='number of poins')
parser.add_argument('--model', type=str, default='', help='model path')    
parser.add_argument('--prim_caps_size', type=int, default=1024, help='number of prim_caps')
parser.add_argument('--prim_vec_size', type=int, default=16, help='scale of prim_vec')
parser.add_argument('--latent_caps_size', type=int, default=64, help='number of latent_caps')
parser.add_argument('--latent_vec_size', type=int, default=64, help='scale of latent_vec')

opt = parser.parse_args()
print(opt)


capsule_net = PointCapsNet(opt.prim_caps_size, opt.prim_vec_size, opt.latent_caps_size, opt.latent_vec_size, opt.num_points)
if opt.model != '':
    capsule_net.load_state_dict(torch.load(opt.model))
else:
    print ('pls set the model path')
    
if USE_CUDA:
    capsule_net = capsule_net.cuda()
capsule_net=capsule_net.eval()

pcd_list=[]
for i in range(opt.latent_caps_size):
    pcd_ = open3d.geometry.PointCloud()
    pcd_list.append(pcd_)
    

#random selected capsules to show their reconstruction with color
#hight_light_caps=[np.random.randint(0, opt.latent_caps_size) for r in range(10)]
hight_light_caps=[29, 40, 16]
#colors = plt.cm.tab20((np.arange(20)).astype(int))
colors = [
  [1, 0, 0],
  [0, 1, 0],
  [0, 0, 1]
]

test_dataset = shapenet_part_loader.PartDataset(classification=True, class_choice="Airplane", npoints=opt.num_points, split='test')

test_dataloader = torch.utils.data.DataLoader(test_dataset, batch_size=opt.batch_size,
                                         shuffle=False, num_workers=4)

capsule_features = [10, 20, 30]
perturbations = [-0.25, 0, 0.25]
rand_grid = Variable(torch.cuda.FloatTensor(8, 2, opt.latent_caps_size))
rand_grid.data.uniform_(0, 1)
for batch_id, data in enumerate(test_dataloader):
    points, _,= data
    if(points.size(0)<opt.batch_size):
        break

    points = Variable(points)
    points = points.transpose(2, 1)
    if USE_CUDA:
        points = points.cuda()

    for highlight in hight_light_caps:
      for feature in capsule_features:
        for perturb in perturbations:
          reconstructions= capsule_net(points, highlight, feature, perturb, rand_grid)
          pointset_id = 1  # because that one seemed to be a good choice
          prc_r_all=reconstructions[pointset_id].transpose(1, 0).contiguous().data.cpu()
          prc_r_all_point=open3d.geometry.PointCloud()
          prc_r_all_point.points = open3d.utility.Vector3dVector(prc_r_all)
          
          colored_re_pointcloud= open3d.geometry.PointCloud()
          jc=0
          for j in range(opt.latent_caps_size):
              current_patch=torch.zeros(int(opt.num_points/opt.latent_caps_size),3)
              for m in range(int(opt.num_points/opt.latent_caps_size)):
                  current_patch[m,]=prc_r_all[opt.latent_caps_size*m+j,] # the reconstructed patch of the capsule m is not saved continuesly in the output reconstruction.
              pcd_list[j].points = open3d.utility.Vector3dVector(current_patch)
              if (j in hight_light_caps):
                  idx = hight_light_caps.index(j)
                  pcd_list[j].paint_uniform_color(colors[idx])
                  jc+=1
              else:
                  pcd_list[j].paint_uniform_color([0.8,0.8,0.8])
              colored_re_pointcloud+=pcd_list[j]
          name = "{}_{}_caps{}_feat{}_perturb_{}.pcd".format(batch_id, pointset_id, highlight, feature, perturb)
          #draw_geometries([colored_re_pointcloud])
          open3d.io.write_point_cloud(name, colored_re_pointcloud)
    break  # because we're observing the perturbation on batch 0
