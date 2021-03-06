import math
import os
import random
import time
from multiprocessing import Process, Manager, Value, Lock, cpu_count

import numpy as np

import utils


def load_world(world_file, gen_size, block_forward, encode_func=utils.encode_world_sigmoid, overlap_x=1, overlap_y=1):
    if not os.path.exists(world_file):
        return

    world = utils.load_world_data_ver3(world_file)
    world_width = world.shape[0]
    world_height = world.shape[1]

    # Check if need to resize width
    if world_width < gen_size[0]:
        # Random placement along x axis
        displace_x = np.random.randint(0, gen_size[0] - world_width + 1)

        world_resized = np.zeros((gen_size[0], world_height), dtype=np.int8)
        world_resized[displace_x:displace_x + world_width, :] = world
        world = world_resized
        world_width = gen_size[0]

    # Check if need to resize height
    if world_height < gen_size[1]:
        # Random placement along y axis
        displace_y = np.random.randint(0, gen_size[1] - world_height + 1)

        world_resized = np.zeros((world_width, gen_size[1]), dtype=np.int8)
        world_resized[:, displace_y:displace_y + world_height] = world
        world = world_resized
        world_height = gen_size[1]

    x_margin = world_width % gen_size[0]
    y_margin = world_height % gen_size[1]

    x_min_increment = overlap_x * gen_size[0]
    y_min_increment = overlap_y * gen_size[1]

    x_offset = np.random.randint(0, x_margin + 1)
    y_offset = np.random.randint(0, y_margin + 1)

    encoded_worlds = []

    x_start = x_offset
    while x_start + gen_size[0] <= world_width:

        y_start = y_offset
        while y_start + gen_size[1] <= world_height:
            x_end = x_start + gen_size[0]
            y_end = y_start + gen_size[1]

            cross_section = world[x_start:x_end, y_start:y_end]

            if is_good_world(cross_section):
                encoded_world = encode_func(block_forward, cross_section)
                encoded_worlds.append(encoded_world)

            y_start += np.random.randint(y_min_increment, gen_size[1] + 1)

        x_start += np.random.randint(x_min_increment, gen_size[0] + 1)
    return encoded_worlds


def load_worlds(load_count, world_directory, gen_size, block_forward, **kwargs):
    world_names = os.listdir(world_directory)
    random.shuffle(world_names)

    thread_count = min(load_count, cpu_count() - 1)

    with Manager() as manager:
        file_queue = manager.Queue()

        for name in world_names:
            file_queue.put(world_directory + name)

        world_array = np.empty((load_count, gen_size[0], gen_size[1], 10), dtype=np.int8)

        world_counter = Value('i', 0)
        thread_lock = Lock()

        threads = []
        for thread in range(thread_count):
            load_thread = WorldLoader(file_queue, manager, world_counter, thread_lock, load_count, gen_size,
                                      block_forward, **kwargs)
            load_thread.start()
            threads.append(load_thread)

        world_index = 0
        for thread in range(len(threads)):
            threads[thread].join()
            print(f'Thread [{thread}] joined.')
            thread_load_queue = threads[thread].get_worlds()
            print(f'Adding thread [{thread}] queue.')
            while thread_load_queue.qsize() > 0:
                world_array[world_index] = thread_load_queue.get()
                world_index += 1

        world_array = world_array[:world_index, :, :, :]
    return world_array


def load_worlds_with_labels(load_count, world_directory, label_dict, gen_size, block_forward, **kwargs):
    thread_count = min(load_count, cpu_count() - 1)

    with Manager() as manager:
        file_queue = manager.Queue()

        dict_keys = []
        for world_id in label_dict.keys():
            dict_keys.append(f'{world_directory}\\{world_id}.world')

        # Shuffle keys
        random.shuffle(dict_keys)
        for key in dict_keys:
            file_queue.put(key)

        world_array = np.empty((load_count, gen_size[0], gen_size[1], 10), dtype=np.int8)
        world_labels = np.empty((load_count, 1), dtype=np.int8)

        world_counter = Value('i', 0)
        thread_lock = Lock()

        threads = []
        for thread in range(thread_count):
            load_thread = WorldLoader(file_queue, manager, world_counter, thread_lock, load_count, gen_size,
                                      block_forward, label_dict=label_dict, **kwargs)
            load_thread.start()
            threads.append(load_thread)

        world_index = 0
        for thread in range(len(threads)):
            threads[thread].join()
            print(f'Thread [{thread}] joined.')
            thread_load_queue = threads[thread].get_worlds()
            label_load_queue = threads[thread].get_labels()
            print(f'Adding thread [{thread}] queue.')
            while thread_load_queue.qsize() > 0:
                world_array[world_index] = thread_load_queue.get()
                world_labels[world_index] = label_load_queue.get()
                world_index += 1

        world_array = world_array[:world_index, :, :, :]
        world_labels = world_labels[:world_index, :]
    return world_array, world_labels


def load_worlds_with_label(load_count, world_directory, label_dict, label_target, gen_size, block_forward, **kwargs):
    thread_count = min(load_count, cpu_count() - 1)

    with Manager() as manager:
        file_queue = manager.Queue()

        dict_keys = []
        for world_id in label_dict.keys():
            dict_keys.append(f'{world_directory}\\{world_id}.world')

        # Shuffle keys
        random.shuffle(dict_keys)
        for key in dict_keys:
            file_queue.put(key)

        world_array = np.empty((load_count, gen_size[0], gen_size[1], 10), dtype=np.int8)

        world_counter = Value('i', 0)
        thread_lock = Lock()

        threads = []
        for thread in range(thread_count):
            load_thread = WorldLoader(file_queue, manager, world_counter, thread_lock, load_count, gen_size,
                                      block_forward, label_dict=label_dict, label_target=label_target, **kwargs)
            load_thread.start()
            threads.append(load_thread)

        world_index = 0
        for thread in range(len(threads)):
            threads[thread].join()
            print(f'Thread [{thread}] joined.')
            thread_load_queue = threads[thread].get_worlds()
            print(f'Adding thread [{thread}] queue.')
            while thread_load_queue.qsize() > 0:
                world_array[world_index] = thread_load_queue.get()
                world_index += 1

        world_array = world_array[:world_index, :, :, :]
    return world_array


def load_worlds_with_files(load_count, world_directory, gen_size, block_forward, **kwargs):
    world_names = os.listdir(world_directory)
    random.shuffle(world_names)

    thread_count = min(load_count, cpu_count() - 1)

    with Manager() as manager:
        file_queue = manager.Queue()

        for name in world_names:
            file_queue.put(world_directory + name)

        world_array = np.empty((load_count, gen_size[0], gen_size[1], 10), dtype=np.int8)
        world_files = []

        world_counter = Value('i', 0)
        thread_lock = Lock()

        threads = []
        for thread in range(thread_count):
            load_thread = WorldLoader(file_queue, manager, world_counter, thread_lock, load_count, gen_size,
                                      block_forward, **kwargs)
            load_thread.start()
            threads.append(load_thread)

        world_index = 0
        for thread in range(len(threads)):
            threads[thread].join()
            print(f'Thread [{thread}] joined.')
            thread_load_queue = threads[thread].get_worlds()
            label_load_queue = threads[thread].get_labels()
            print(f'Adding thread [{thread}] queue.')
            while thread_load_queue.qsize() > 0:
                world_array[world_index] = thread_load_queue.get()
                world_files.append(label_load_queue.get())
                world_index += 1

        world_array = world_array[:world_index, :, :, :]
    return world_array, world_files


def load_worlds_with_minimaps(load_count, world_directory, gen_size, block_forward, minimap_values, **kwargs):
    world_names = os.listdir(world_directory)
    random.shuffle(world_names)

    thread_count = min(load_count, cpu_count() - 1)

    with Manager() as manager:
        file_queue = manager.Queue()

        for name in world_names:
            file_queue.put(world_directory + name)

        world_array = np.empty((load_count, gen_size[0], gen_size[1], 10), dtype=np.int8)
        world_minimaps = np.empty((load_count, gen_size[0], gen_size[1], 3), dtype=float)

        world_counter = Value('i', 0)
        thread_lock = Lock()

        threads = []
        for thread in range(thread_count):
            load_thread = WorldLoader(file_queue, manager, world_counter, thread_lock, load_count, gen_size,
                                      block_forward, minimap_values=minimap_values, load_minimap=True, **kwargs)
            load_thread.start()
            threads.append(load_thread)

        world_index = 0
        for thread in range(len(threads)):
            threads[thread].join()
            print(f'Thread [{thread}] joined.')
            thread_load_queue = threads[thread].get_worlds()
            minimap_load_queue = threads[thread].get_minimaps()
            print(f'Adding thread [{thread}] queue.')
            while thread_load_queue.qsize() > 0:
                world_array[world_index] = thread_load_queue.get()
                world_minimaps[world_index] = minimap_load_queue.get()
                world_index += 1

        world_array = world_array[:world_index, :, :, :]
        world_minimaps = world_minimaps[:world_index, :, :, :]
    return world_array, world_minimaps


def load_minimaps(load_count, world_directory, gen_size, block_forward, minimap_values, **kwargs):
    world_names = os.listdir(world_directory)
    random.shuffle(world_names)

    thread_count = min(load_count, cpu_count() - 1)

    with Manager() as manager:
        file_queue = manager.Queue()

        for name in world_names:
            file_queue.put(world_directory + name)

        world_minimaps = np.empty((load_count, gen_size[0], gen_size[1], 3), dtype=float)

        world_counter = Value('i', 0)
        thread_lock = Lock()

        threads = []
        for thread in range(thread_count):
            load_thread = WorldLoader(file_queue, manager, world_counter, thread_lock, load_count, gen_size,
                                      block_forward, minimap_values=minimap_values, load_minimap=True, skip_world=True,
                                      **kwargs)
            load_thread.start()
            threads.append(load_thread)

        world_index = 0
        for thread in range(len(threads)):
            threads[thread].join()
            print(f'Thread [{thread}] joined.')
            minimap_load_queue = threads[thread].get_minimaps()
            print(f'Adding thread [{thread}] queue.')
            while minimap_load_queue.qsize() > 0 and world_index < world_minimaps.shape[0]:
                world_minimaps[world_index] = minimap_load_queue.get()
                world_index += 1

        world_minimaps = world_minimaps[:world_index, :, :, :]
    return world_minimaps


def is_good_world(cross_section):
    # - Count blocks
    # - Diversity of blocks
    edited_blocks = 0
    distinct_ids = []
    width = cross_section.shape[0]
    height = cross_section.shape[1]
    for x in range(width):
        for y in range(height):
            block = cross_section[x, y]
            if block != 0:
                edited_blocks += 1
            if block not in distinct_ids:
                distinct_ids.append(block)

    total_size = width * height
    required = int(0.5 * total_size)
    return edited_blocks >= required and len(distinct_ids) >= 6


def is_good_label_world(cross_section):
    # - Count blocks
    edited_blocks = 0
    width = cross_section.shape[0]
    height = cross_section.shape[1]
    for x in range(width):
        for y in range(height):
            block = cross_section[x, y]
            if block != 0:
                edited_blocks += 1

    total_size = width * height
    required = int(0.2 * total_size)
    return edited_blocks >= required


class WorldLoader(Process):
    time_pt_index = 0
    time_pt_cnt = 0

    def update_estimate(self, time_points, time0, time1, cnt0, cnt1):
        cnt_delta = cnt1 - cnt0
        worlds_left = self.target_count - self.world_counter.value
        if cnt_delta != 0:
            time_points[self.time_pt_index] = (time1 - time0) / cnt_delta
            self.time_pt_index = (self.time_pt_index + 1) % len(time_points)
            if self.time_pt_index < len(time_points):
                self.time_pt_cnt += 1

        if self.time_pt_cnt > 0:
            time_left_sec = np.average(time_points[0:self.time_pt_cnt]) * worlds_left
            time_left = time_left_sec / 60.0
            time_left_minutes = int(time_left)
            time_left_minutes_frac = time_left - time_left_minutes
            time_left_seconds = int(math.ceil(time_left_minutes_frac * 60))
            if time_left_minutes > 1:
                return f'ETA {time_left_minutes} minutes'
            elif time_left_minutes == 1:
                return 'ETA 1 minute'
            else:
                return f'ETA {time_left_seconds} seconds'  # 'ETA <1 Minute'
        else:
            return ''

    def load_world(self, world_file):
        if not os.path.exists(world_file):
            return

        world = utils.load_world_data_ver3(world_file)
        world_width = world.shape[0]
        world_height = world.shape[1]

        label = None
        if self.label_dict is not None:
            world_id = utils.get_world_id(world_file)
            if world_id in self.label_dict:
                label = self.label_dict[world_id]
                if self.label_target is not None and label != self.label_target:
                    # Label does not match label_target
                    return
            else:
                # No label for world, return
                return

        # Check if need to resize width
        if world_width < self.gen_size[0]:
            # Random placement along x axis
            displace_x = np.random.randint(0, self.gen_size[0] - world_width + 1)

            world_resized = np.zeros((self.gen_size[0], world_height), dtype=np.int8)
            world_resized[displace_x:displace_x + world_width, :] = world
            world = world_resized
            world_width = self.gen_size[0]

        # Check if need to resize height
        if world_height < self.gen_size[1]:
            # Random placement along y axis
            displace_y = np.random.randint(0, self.gen_size[1] - world_height + 1)

            world_resized = np.zeros((world_width, self.gen_size[1]), dtype=np.int8)
            world_resized[:, displace_y:displace_y + world_height] = world
            world = world_resized
            world_height = self.gen_size[1]

        x_margin = world_width % self.gen_size[0]
        y_margin = world_height % self.gen_size[1]

        x_min_increment = self.overlap_x * self.gen_size[0]
        y_min_increment = self.overlap_y * self.gen_size[1]

        x_offset = np.random.randint(0, x_margin + 1)
        y_offset = np.random.randint(0, y_margin + 1)

        x_start = x_offset
        while x_start + self.gen_size[0] <= world_width:

            y_start = y_offset
            while y_start + self.gen_size[1] <= world_height:
                x_end = x_start + self.gen_size[0]
                y_end = y_start + self.gen_size[1]
                cross_section = world[x_start:x_end, y_start:y_end]

                if (self.label_dict is not None and is_good_label_world(cross_section)) or \
                        (self.label_dict is None and is_good_world(cross_section)):

                    if self.skip_world:
                        if self.load_minimap and self.world_counter.value < self.target_count:
                            self.thread_lock.acquire()
                            minimap = utils.encode_world_minimap(self.minimap_values, cross_section)
                            self.minimap_queue.put(minimap)
                            self.world_counter.value += 1
                            self.thread_lock.release()

                        y_start += np.random.randint(y_min_increment, self.gen_size[1] + 1)
                        continue

                    encoded_world0 = self.encode_func(self.block_forward, cross_section)
                    encoded_worlds = [encoded_world0]

                    self.thread_lock.acquire()

                    local_index = 0
                    while self.world_counter.value < self.target_count and local_index < len(encoded_worlds):
                        self.load_queue.put(encoded_worlds[local_index])

                        if self.label_dict is not None:
                            self.label_queue.put(label)
                        else:
                            self.label_queue.put(world_file)

                        if self.load_minimap and self.minimap_values is not None:
                            minimap = utils.encode_world_minimap(self.minimap_values, cross_section)
                            self.minimap_queue.put(minimap)

                        self.world_counter.value += 1
                        local_index += 1

                    self.thread_lock.release()

                    if local_index == 0:
                        break

                y_start += np.random.randint(y_min_increment, self.gen_size[1] + 1)

            x_start += np.random.randint(x_min_increment, self.gen_size[0] + 1)

    def __init__(self, file_queue, manager, counter, tlock, target_count, gen_size, block_forward, **kwargs):
        Process.__init__(self)
        self.file_queue = file_queue
        self.load_queue = manager.Queue()
        self.label_queue = manager.Queue()
        self.minimap_queue = manager.Queue()
        self.world_counter = counter
        self.thread_lock = tlock
        self.target_count = int(target_count)
        self.gen_size = gen_size
        self.block_forward = block_forward

        self.encode_func = kwargs.get('encode_func', utils.encode_world_sigmoid)
        self.label_dict = kwargs.get('label_dict', None)

        self.label_target = kwargs.get('label_target', None)
        self.overlap_x = kwargs.get('overlap_x', 1)
        self.overlap_y = kwargs.get('overlap_y', 1)

        self.load_minimap = kwargs.get('load_minimap', False)
        self.minimap_values = kwargs.get('minimap_values', None)
        self.skip_world = kwargs.get('skip_world', False)

        if self.skip_world and not self.load_minimap:
            raise Exception('Nothing to load.')

        self.daemon = True

    def run(self):
        time_points = np.array([0.] * 200)
        while not self.file_queue.empty() and self.world_counter.value < self.target_count:
            world_file = self.file_queue.get()
            time0 = time.time()
            cnt0 = self.world_counter.value
            self.load_world(world_file)
            time1 = time.time()
            cnt1 = self.world_counter.value
            time_est_str = self.update_estimate(time_points, time0, time1, cnt0, cnt1)
            print(f'Loaded ({self.world_counter.value}/{self.target_count}) {time_est_str}')
            if self.world_counter.value >= self.target_count:
                break
        print('Done loading.')

    def get_worlds(self):
        return self.load_queue

    def get_labels(self):
        return self.label_queue

    def get_minimaps(self):
        return self.minimap_queue
