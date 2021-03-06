import os

import keras
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import numpy as np
from keras.layers import Dense, SpatialDropout2D
from keras.layers.advanced_activations import LeakyReLU
from keras.layers.convolutional import Conv2D
from keras.layers.normalization import BatchNormalization
from keras.layers.pooling import GlobalAveragePooling2D, MaxPooling2D
from keras.models import Sequential, load_model
from keras.optimizers import Adam

import utils
from loadworker import load_world, load_worlds_with_labels, load_worlds_with_files


def build_classifier(size):
    model = Sequential(name='pro_classifier')

    f = 64
    s = size

    while s > 7:
        if s == size:
            model.add(Conv2D(filters=f, kernel_size=7, strides=1, padding='same', input_shape=(size, size, 10)))
        else:
            model.add(Conv2D(filters=f, kernel_size=7, strides=1, padding='same'))

        model.add(BatchNormalization(momentum=0.8, axis=3))
        model.add(LeakyReLU())

        model.add(Conv2D(filters=f, kernel_size=3, strides=1, padding='same'))
        model.add(BatchNormalization(momentum=0.8, axis=3))
        model.add(LeakyReLU())

        model.add(MaxPooling2D(pool_size=(2, 2)))
        model.add(SpatialDropout2D(0.15))

        f = f * 2
        s = s // 2

    model.add(GlobalAveragePooling2D())

    model.add(Dense(1, activation='sigmoid'))
    return model


def train(epochs, batch_size, world_count, dict_src_name, version_name=None, initial_epoch=0):
    cur_dir = os.getcwd()
    res_dir = os.path.abspath(os.path.join(cur_dir, '..', 'res'))
    all_models_dir = os.path.abspath(os.path.join(cur_dir, '..', 'models'))
    model_dir = utils.check_or_create_local_path('pro_classifier', all_models_dir)

    utils.delete_empty_versions(model_dir, 1)
    no_version = version_name is None
    if no_version:
        latest = utils.get_latest_version(model_dir)
        version_name = f'ver{latest + 1}'

    version_dir = utils.check_or_create_local_path(version_name, model_dir)
    graph_dir = utils.check_or_create_local_path('graph', model_dir)
    graph_version_dir = utils.check_or_create_local_path(version_name, graph_dir)

    model_save_dir = utils.check_or_create_local_path('models', version_dir)

    print('Saving source...')
    utils.save_source_to_dir(version_dir)

    print('Loading encoding dictionaries...')
    block_forward, block_backward = utils.load_encoding_dict(res_dir, 'blocks_optimized')

    print('Building model from scratch...')
    c_optim = Adam(lr=0.0001)

    size = 64
    c = build_classifier(size)
    # c = build_resnet50(1)
    # c = build_wide_resnet(input_dim=(size, size, 10), nb_classes=1, N=2, k=1, dropout=0.1)

    c.summary()
    c.compile(loss='binary_crossentropy', optimizer=c_optim, metrics=['accuracy'])

    print('Loading labels...')
    label_dict = utils.load_label_dict(res_dir, dict_src_name)

    print('Loading worlds...')
    x, y_raw = load_worlds_with_labels(world_count, f'{res_dir}\\worlds\\', label_dict, (size, size),
                                       block_forward)

    y = utils.convert_labels_binary(y_raw, epsilon=0)

    # Create callback for automatically saving best model based on highest regular accuracy
    check_best_acc = keras.callbacks.ModelCheckpoint(f'{model_save_dir}\\best_acc.h5', monitor='acc', verbose=0,
                                                     save_best_only=True, save_weights_only=False, mode='max',
                                                     period=1)

    # Create callback for automatically saving latest model so training can be resumed. Saves every epoch
    latest_h5_callback = keras.callbacks.ModelCheckpoint(f'{model_save_dir}\\latest.h5', verbose=0,
                                                         save_best_only=False,
                                                         save_weights_only=False, mode='auto', period=1)

    # Create callback for automatically saving latest weights so training can be resumed. Saves every epoch
    latest_weights_callback = keras.callbacks.ModelCheckpoint(f'{model_save_dir}\\latest.weights', verbose=0,
                                                              save_best_only=False,
                                                              save_weights_only=True, mode='auto', period=1)

    # Create callback for tensorboard
    tb_callback = keras.callbacks.TensorBoard(log_dir=graph_version_dir, batch_size=batch_size, write_graph=False,
                                              write_grads=True)

    callback_list = [check_best_acc, latest_h5_callback, latest_weights_callback, tb_callback]

    # Train model
    c.fit(x, y, batch_size, epochs, initial_epoch=initial_epoch, callbacks=callback_list, validation_split=0.2)


def predict(network_ver, dict_src_name):
    cur_dir = os.getcwd()
    res_dir = os.path.abspath(os.path.join(cur_dir, '..', 'res'))
    all_models_dir = os.path.abspath(os.path.join(cur_dir, '..', 'models'))
    model_dir = utils.check_or_create_local_path('pro_classifier', all_models_dir)
    version_dir = utils.check_or_create_local_path(network_ver, model_dir)
    model_save_dir = utils.check_or_create_local_path('models', version_dir)

    classifications_dir = utils.check_or_create_local_path('classifications', model_dir)
    utils.delete_files_in_path(classifications_dir)

    pro_dir = utils.check_or_create_local_path('pro', classifications_dir)
    notpro_dir = utils.check_or_create_local_path('notpro', classifications_dir)

    print('Loading model...')
    classifier = load_model(f'{model_save_dir}\\latest.h5')

    print('Loading block images...')
    block_images = utils.load_block_images(res_dir)

    print('Loading encoding dictionaries...')
    block_forward, block_backward = utils.load_encoding_dict(res_dir, 'blocks_optimized')

    x_data, x_files = load_worlds_with_files(5000, f'{res_dir}\\worlds\\', (112, 112), block_forward)

    x_labeled = utils.load_label_dict(res_dir, dict_src_name)

    batch_size = 50
    batches = x_data.shape[0] // batch_size

    for batch_index in range(batches):
        x_batch = x_data[batch_index * batch_size:(batch_index + 1) * batch_size]
        y_batch = classifier.predict(x_batch)

        for world in range(batch_size):
            g_index = (batch_index * batch_size) + world
            world_file = x_files[g_index]
            world_id = utils.get_world_id(world_file)

            # Ignore worlds we've already labeled
            if world_id in x_labeled:
                continue

            prediction = y_batch[world]

            world_data = utils.load_world_data_ver3(f'{res_dir}\\worlds\\{world_id}.world')

            if prediction[0] < 0.5:
                utils.save_world_preview(block_images, world_data, f'{notpro_dir}\\{world_id}.png')
            else:
                utils.save_world_preview(block_images, world_data, f'{pro_dir}\\{world_id}.png')


def predict_sample_matlab(network_ver, dict_src_name, cols, rows):
    cur_dir = os.getcwd()
    res_dir = os.path.abspath(os.path.join(cur_dir, '..', 'res'))
    all_models_dir = os.path.abspath(os.path.join(cur_dir, '..', 'models'))
    model_dir = utils.check_or_create_local_path('pro_classifier', all_models_dir)
    version_dir = utils.check_or_create_local_path(network_ver, model_dir)
    model_save_dir = utils.check_or_create_local_path('models', version_dir)

    plots_dir = utils.check_or_create_local_path('plots', model_dir)
    utils.delete_files_in_path(plots_dir)

    print('Loading model...')
    classifier = load_model(f'{model_save_dir}\\latest.h5')

    print('Loading block images...')
    block_images = utils.load_block_images(res_dir)

    print('Loading encoding dictionaries...')
    block_forward, block_backward = utils.load_encoding_dict(res_dir, 'blocks_optimized')

    x_labeled = utils.load_label_dict(res_dir, dict_src_name)
    x_worlds = os.listdir(f'{res_dir}\\worlds\\')
    np.random.shuffle(x_worlds)

    world_size = classifier.input_shape[1]
    dpi = 96
    hpixels = 320 * cols
    hfigsize = hpixels / dpi
    vpixels = 330 * rows
    vfigsize = vpixels / dpi
    fig = plt.figure(figsize=(hfigsize, vfigsize), dpi=dpi)

    sample_num = 0
    pro_score_floor = 0
    pro_score_ceiling = 1.0 / (rows * cols)
    for world_filename in x_worlds:
        world_file = os.path.join(f'{res_dir}\\worlds\\', world_filename)
        world_id = utils.get_world_id(world_filename)
        if world_id not in x_labeled:

            # Load world and save preview
            encoded_regions = load_world(world_file, (world_size, world_size), block_forward)
            if len(encoded_regions) == 0:
                continue

            # Create prediction
            batch_input = np.empty((1, world_size, world_size, 10), dtype=np.int8)
            batch_input[0] = encoded_regions[0]
            batch_score = classifier.predict(batch_input)
            pro_score = batch_score[0][0]

            if pro_score < pro_score_floor or pro_score > pro_score_ceiling:
                continue

            decoded_region = utils.decode_world_sigmoid(block_backward, encoded_regions[0])
            utils.save_world_preview(block_images, decoded_region, f'{plots_dir}\\preview{sample_num}.png')

            pro_score_floor += 1.0 / (rows * cols)
            pro_score_ceiling += 1.0 / (rows * cols)

            # Create plot
            img = mpimg.imread(f'{plots_dir}\\preview{sample_num}.png')

            subplt = fig.add_subplot(rows, cols, sample_num + 1)
            subplt.set_title(world_id)
            subplt.set_xlabel('P = %.2f%%' % (pro_score * 100))

            no_labels = 2  # how many labels to see on axis x
            step = (16 * world_size) / (no_labels - 1)  # step between consecutive labels
            positions = np.arange(0, (16 * world_size) + 1, step)  # pixel count at label position
            labels = positions // 16
            plt.xticks(positions, labels)
            plt.yticks(positions, labels)
            plt.imshow(img)

            print(f'Adding plot {sample_num + 1} of {rows * cols}')

            sample_num += 1
            if sample_num >= rows * cols:
                break

    print('Saving figure...')
    fig.tight_layout()
    fig.savefig(f'{plots_dir}\\plot.png', transparent=True)


def add_training_data(current_label_dict):
    cur_dir = os.getcwd()
    res_dir = os.path.abspath(os.path.join(cur_dir, '..', 'res'))
    all_models_dir = os.path.abspath(os.path.join(cur_dir, '..', 'models'))
    model_dir = utils.check_or_create_local_path('pro_classifier', all_models_dir)
    classifications_dir = utils.check_or_create_local_path('classifications', model_dir)
    pro_dir = utils.check_or_create_local_path('pro', classifications_dir)
    notpro_dir = utils.check_or_create_local_path('notpro', classifications_dir)

    notpro_worlds = os.listdir(notpro_dir)
    pro_worlds = os.listdir(pro_dir)

    orig_dict = utils.load_label_dict(res_dir, current_label_dict)
    new_dict = utils.load_label_dict(res_dir, current_label_dict)

    for notpro_world in notpro_worlds:
        notpro_id = utils.get_world_id(notpro_world)
        if notpro_id not in orig_dict:
            new_dict[notpro_id] = 0

    for pro_world in pro_worlds:
        pro_id = utils.get_world_id(pro_world)
        new_dict[pro_id] = 1

    utils.save_label_dict(classifications_dir, 'test', new_dict)


def save_current_labels(current_label_dict):
    cur_dir = os.getcwd()
    res_dir = os.path.abspath(os.path.join(cur_dir, '..', 'res'))
    all_models_dir = os.path.abspath(os.path.join(cur_dir, '..', 'models'))
    model_dir = utils.check_or_create_local_path('pro_classifier', all_models_dir)
    notpro_dir = utils.check_or_create_local_path('notpro', model_dir)
    pro_dir = utils.check_or_create_local_path('pro', model_dir)

    print('Loading block images...')
    block_images = utils.load_block_images(res_dir)

    print('Loading label dict...')
    x_labeled = utils.load_label_dict(res_dir, current_label_dict)

    saved = 0
    for x_world in x_labeled:
        label = x_labeled[x_world]

        if os.path.exists(f'{pro_dir}\\{x_world}.png') or os.path.exists(f'{notpro_dir}\\{x_world}.png'):
            saved += 1
            continue

        world_file = f'{res_dir}\\worlds\\{x_world}.world'
        world_data = utils.load_world_data_ver3(world_file)

        if label == 1:
            utils.save_world_preview(block_images, world_data, f'{pro_dir}\\{x_world}.png')
        else:
            utils.save_world_preview(block_images, world_data, f'{notpro_dir}\\{x_world}.png')

        saved += 1
        print(f'Saved {saved} of {len(x_labeled)} world previews')


def main():
    train(epochs=100, batch_size=32, world_count=125000, dict_src_name='pro_labels_b')
    # predict('ver9', dict_src_name='pro_labels_b')
    # add_training_data('pro_labels_b')
    # predict_sample_matlab('ver38', dict_src_name='pro_labels_b', cols=3, rows=3)
    # save_current_labels('pro_labels_b')


if __name__ == '__main__':
    main()
