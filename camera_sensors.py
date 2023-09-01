#!/usr/bin/env python
import glob
import os
import sys

try:
    sys.path.append(glob.glob('../carla/dist/carla-*%d.%d-%s.egg' % (
        sys.version_info.major,
        sys.version_info.minor,
        'win-amd64' if os.name == 'nt' else 'linux-x86_64'))[0])
except IndexError:
    pass

import carla


import math 
import random 
import time 
import numpy as np
import cv2

# Connect the client and set up bp library and spawn points
client = carla.Client('localhost', 2000) 
world = client.get_world()
bp_lib = world.get_blueprint_library()  
spawn_points = world.get_map().get_spawn_points() 



# Add the ego vehicle
vehicle_bp = bp_lib.find('vehicle.lincoln.mkz_2020') 
vehicle = world.try_spawn_actor(vehicle_bp, spawn_points[79])

# Move the spectator behind the vehicle to view it
spectator = world.get_spectator() 
transform = carla.Transform(vehicle.get_transform().transform(carla.Location(x=-4,z=2.5)),vehicle.get_transform().rotation) 
spectator.set_transform(transform)

# Add traffic
for i in range(50): 
    vehicle_bp = random.choice(bp_lib.filter('vehicle')) 
    npc = world.try_spawn_actor(vehicle_bp, random.choice(spawn_points)) 




# Set traffic in motion
for v in world.get_actors().filter('*vehicle*'): 
    v.set_autopilot(True) 



# Set initial camera translation
camera_init_trans = carla.Transform(carla.Location(z=2))

# Add one of each type of camera
camera_bp = bp_lib.find('sensor.camera.rgb') 
camera = world.spawn_actor(camera_bp, camera_init_trans, attach_to=vehicle)

sem_camera_bp = bp_lib.find('sensor.camera.semantic_segmentation') 
sem_camera = world.spawn_actor(sem_camera_bp, camera_init_trans, attach_to=vehicle)

inst_camera_bp = bp_lib.find('sensor.camera.instance_segmentation') 
inst_camera = world.spawn_actor(inst_camera_bp, camera_init_trans, attach_to=vehicle)

depth_camera_bp = bp_lib.find('sensor.camera.depth') 
depth_camera = world.spawn_actor(depth_camera_bp, camera_init_trans, attach_to=vehicle)

dvs_camera_bp = bp_lib.find('sensor.camera.dvs') 
dvs_camera = world.spawn_actor(dvs_camera_bp, camera_init_trans, attach_to=vehicle)

opt_camera_bp = bp_lib.find('sensor.camera.optical_flow') 
opt_camera = world.spawn_actor(opt_camera_bp, camera_init_trans, attach_to=vehicle)


# Define respective callbacks
def rgb_callback(image, data_dict):
    data_dict['rgb_image'] = np.reshape(np.copy(image.raw_data), (image.height, image.width, 4))
    
def sem_callback(image, data_dict):
    image.convert(carla.ColorConverter.CityScapesPalette)
    data_dict['sem_image'] = np.reshape(np.copy(image.raw_data), (image.height, image.width, 4))

def inst_callback(image, data_dict):
    data_dict['inst_image'] = np.reshape(np.copy(image.raw_data), (image.height, image.width, 4))

def depth_callback(image, data_dict):
    image.convert(carla.ColorConverter.LogarithmicDepth)
    data_dict['depth_image'] = np.reshape(np.copy(image.raw_data), (image.height, image.width, 4))
    
def opt_callback(data, data_dict):
    image = data.get_color_coded_flow()
    img = np.reshape(np.copy(image.raw_data), (image.height, image.width, 4))
    img[:,:,3] = 255
    data_dict['opt_image'] = img
    
def dvs_callback(data, data_dict):
    dvs_events = np.frombuffer(data.raw_data, dtype=np.dtype([
                ('x', np.uint16), ('y', np.uint16), ('t', np.int64), ('pol', np.bool_)]))
    data_dict['dvs_image'] = np.zeros((data.height, data.width, 4), dtype=np.uint8)
    dvs_img = np.zeros((data.height, data.width, 3), dtype=np.uint8)
    dvs_img[dvs_events[:]['y'], dvs_events[:]['x'], dvs_events[:]['pol'] * 2] = 255
    data_dict['dvs_image'][:,:,0:3] = dvs_img
    



# Initialise parameters and data
image_w = camera_bp.get_attribute("image_size_x").as_int()
image_h = camera_bp.get_attribute("image_size_y").as_int()


sensor_data = {'rgb_image': np.zeros((image_h, image_w, 4)),
               'sem_image': np.zeros((image_h, image_w, 4)),
               'depth_image': np.zeros((image_h, image_w, 4)),
               'dvs_image': np.zeros((image_h, image_w, 4)),
               'opt_image': np.zeros((image_h, image_w, 4)), 
               'inst_image': np.zeros((image_h, image_w, 4))}

# OpenCV named window for display
cv2.namedWindow('All cameras', cv2.WINDOW_AUTOSIZE)

# Tile all data in one array
top_row = np.concatenate((sensor_data['rgb_image'], sensor_data['sem_image'], sensor_data['inst_image']), axis=1)
lower_row = np.concatenate((sensor_data['depth_image'], sensor_data['dvs_image'], sensor_data['opt_image']), axis=1)
tiled = np.concatenate((top_row, lower_row), axis=0)

# Display with imshow
cv2.imshow('All cameras',tiled)
cv2.waitKey(1)

# Set sensors recording
camera.listen(lambda image: rgb_callback(image, sensor_data))
sem_camera.listen(lambda image: sem_callback(image, sensor_data))
inst_camera.listen(lambda image: inst_callback(image, sensor_data))
depth_camera.listen(lambda image: depth_callback(image, sensor_data))
dvs_camera.listen(lambda image: dvs_callback(image, sensor_data))
opt_camera.listen(lambda image: opt_callback(image, sensor_data))

# Indefinite while loop
while True:
    
    # Tile camera images into one array
    top_row = np.concatenate((sensor_data['rgb_image'], sensor_data['sem_image'], sensor_data['inst_image']), axis=1)
    lower_row = np.concatenate((sensor_data['depth_image'], sensor_data['dvs_image'], sensor_data['opt_image']), axis=1)
    tiled = np.concatenate((top_row, lower_row), axis=0)
       
    # Dispaly with imshow
    cv2.imshow('All cameras',tiled)
    
    # Break loop if user presses q
    if cv2.waitKey(1) == ord('q'):
        break

# Stop sensors and destroy OpenCV window
camera.stop()
sem_camera.stop()
inst_camera.stop()
depth_camera.stop()
dvs_camera.stop()
opt_camera.stop()
cv2.destroyAllWindows()