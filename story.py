import numpy as np

import tensorflow as tf
from tensorflow import keras

from src.layers import EmbeddingSim, EmbeddingRet, PositionEmbedding, LayerNormalization, _get_encoder_component, gelu, ScaledDotProductAttention, MultiHeadAttention, FeedForward
from src import encoder
from src import net
from src import utils

from memory import mem_compile

def init_model(args):
        args.input_stack = []

        if args.gpu_index:
                physdevs = tf.config.list_physical_devices('GPU')
                tf.config.experimental.set_virtual_device_configuration(physdevs[args.gpu_index], [tf.config.LogicalDeviceConfiguration(args.gpu_max_mem)])
        
        tf.compat.v1.disable_eager_execution()

        if not args.model_dir:
                print('model path must be provided!')
                exit()

        if not args.custom_model:
                args.model_path = args.model_dir + "model.ckpt"
        else:
                args.model_path = args.custom_model

        args.json_hparams = args.model_dir + "hparams.json"
        args.json_encoder = args.model_dir + "encoder.json"
        args.vocab_bpe = args.model_dir + "vocab.bpe"

        args.enc = encoder.get_encoder(args.json_encoder, args.vocab_bpe)

        if args.model_path.split('.')[-1] == 'h5':
                args.model = keras.models.load_model(
                args.model_path,
                custom_objects={'EmbeddingSim': EmbeddingSim,
                                'EmbeddingRet': EmbeddingRet,
                                'PositionEmbedding': PositionEmbedding,
                                'LayerNormalization': LayerNormalization,
                                'ScaledDotProductAttention': ScaledDotProductAttention,
                                'MultiHeadAttention': MultiHeadAttention,
                                'FeedForward': FeedForward,
                                'gelu': gelu,
                                'loss': net.loss})
        elif args.model_path.split('.')[-1] == 'ckpt':
                args.model_ckpt = args.model_path
                args.model = net.create_model(args)
                args.model = net.load_weights(args.model, args)
                args.model.compile(optimizer=keras.optimizers.Adam(), loss=net.loss)
        else:
                print('Unsupported custom model format!')
                exit()
        
        args.model.trainable = False

def run_model(args, input_str):
        # Push the input_str into a list, and popping off the last members if it is past args.past_length

        args.input_stack.append(input_str)

        # if past_length is 0, remember indefinitely.
        if args.past_length != 0:
                if len(args.input_stack) > args.past_length:
                        args.input_stack.pop()

        input_str = args.context + '\n' + mem_compile(input_str) + '\n'
        for i in args.input_stack:
                input_str = input_str + i
        
        # TODO: Cleanup code since batch_size is not necessary.

        input_str = input_str.replace("\\'", "'")

        input_data = [args.enc.encode(input_str)] * args.batch_size
        start_length = [len(data) for data in input_data]
        flag_stop = [False] * args.batch_size
        stop = False

        # Inference the model..
        for shift in range(args.output_length):
                output_data = args.model.predict(np.array(input_data))
                for index in range(args.batch_size):
                        if not flag_stop[index]:
                                probs = [(prob, i) for i, prob in enumerate(output_data[index, start_length[index] + shift - 1])]
                                probs.sort(reverse=True)
                                if args.nucleus:
                                        next_token = utils.find_top_p(probs, args.top_p, args.temperature)
                                else:
                                        next_token = utils.find_top_p(probs, args.top_k, args.temperature)        
                                
                                input_data[index].append(next_token)
                                if next_token == 50256:
                                        flag_stop[index] = True
                        else:
                                input_data[index].append(50256)
                        
                        output = args.enc.decode(input_data[index])
                        output = output[len(input_str):]

                        for i, stopchar in enumerate(output):
                                if ('\n' == stopchar) and (i > 0):
                                        stop = True

                if stop:
                        args.input_stack.append(output)
                        break

        return output
