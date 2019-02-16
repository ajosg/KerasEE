import os

import keras
import numpy as np
from keras.layers.convolutional import Conv2D
from keras.models import Sequential
from keras.optimizers import Adam

import utils
from loadworker import load_worlds_with_minimaps


def build_translator(size):
    # Takes in a real world, and aims to draw the minimap
    # This is needed, so we can train the animator and get a loss
    # even though we already can generate a perfect minimap, it has to learn to
    # figure out which blocks create which colors itself, we cannot do that for it
    # Output is minimap

    model = Sequential()

    # model.add(Reshape(input_shape=(64, 64, 10), target_shape=(64 * 64 * 10,)))
    # model.add(Dense(units=64 * 64 * 3, activation='sigmoid'))
    # model.add(Reshape(target_shape=(64, 64, 3)))

    model.add(Conv2D(256, kernel_size=(1, 1), strides=(1, 1), padding='same', input_shape=(size, size, 10)))
    model.add(Conv2D(512, kernel_size=(1, 1), strides=(1, 1), padding='same', input_shape=(size, size, 10)))
    model.add(Conv2D(3, kernel_size=(1, 1), strides=(1, 1), padding='same'))

    model.summary()
    return model


def get_minimaps(worlds, block_backward, minimap_values):
    # Get minimaps
    batch_size = worlds.shape[0]
    world_width = worlds.shape[1]
    world_height = worlds.shape[2]
    minimaps = np.zeros((batch_size, world_width, world_height, 3), dtype=float)

    for i in range(batch_size):
        decoded_world = utils.decode_world_sigmoid(block_backward, worlds[i])
        minimaps[i] = utils.encode_world_minimap2d(minimap_values, decoded_world)

    return minimaps


def train(epochs, batch_size, world_count, version_name=None, initial_epoch=0):
    cur_dir = os.getcwd()
    res_dir = os.path.abspath(os.path.join(cur_dir, '..', 'res'))
    all_models_dir = os.path.abspath(os.path.join(cur_dir, '..', 'models'))
    model_dir = utils.check_or_create_local_path('translator', all_models_dir)

    utils.delete_empty_versions(model_dir, 1)
    no_version = version_name is None
    if no_version:
        latest = utils.get_latest_version(model_dir)
        version_name = 'ver%s' % (latest + 1)

    version_dir = utils.check_or_create_local_path(version_name, model_dir)
    graph_dir = utils.check_or_create_local_path('graph', model_dir)
    graph_version_dir = utils.check_or_create_local_path(version_name, graph_dir)

    model_save_dir = utils.check_or_create_local_path('models', version_dir)

    print('Saving source...')
    utils.save_source_to_dir(version_dir)

    print('Loading minimap values...')
    minimap_values = utils.load_minimap_values(res_dir)

    print('Loading block images...')
    block_images = utils.load_block_images(res_dir)

    print('Loading encoding dictionaries...')
    block_forward, block_backward = utils.load_encoding_dict(res_dir, 'blocks_colored')

    print('Building model from scratch...')
    optim = Adam(lr=0.0001)
    translator = build_translator(112)
    translator.compile(optim, loss='mse')

    print('Loading worlds...')
    x_train, y_train = load_worlds_with_minimaps(world_count, '%s\\worlds\\' % res_dir, (112, 112), block_forward,
                                                 minimap_values)

    # Create callback for automatically saving lastest model so training can be resumed. Saves every epoch
    latest_h5_callback = keras.callbacks.ModelCheckpoint('%s\\latest.h5' % model_save_dir, verbose=0,
                                                         save_best_only=False,
                                                         save_weights_only=False, mode='auto', period=1)

    # Create callback for automatically saving lastest weights so training can be resumed. Saves every epoch
    latest_weights_callback = keras.callbacks.ModelCheckpoint('%s\\latest.weights' % model_save_dir, verbose=0,
                                                              save_best_only=False,
                                                              save_weights_only=True, mode='auto', period=1)

    # Create callback for tensorboard
    tb_callback = keras.callbacks.TensorBoard(log_dir=graph_version_dir, batch_size=batch_size, write_graph=False,
                                              write_grads=True)

    callback_list = [latest_h5_callback, latest_weights_callback, tb_callback]

    translator.fit(x_train, y_train, batch_size, epochs, callbacks=callback_list)


def main():
    train(epochs=13, batch_size=50, world_count=25000)
    # train(epochs=13, batch_size=32, world_count=1000)
    # predict('ver9', dict_src_name='pro_labels')


if __name__ == '__main__':
    main()
