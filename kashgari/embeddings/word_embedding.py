# encoding: utf-8

# author: BrikerMan
# contact: eliyar917@gmail.com
# blog: https://eliyar.biz

# file: w2v_embedding.py
# time: 2019-05-20 17:32

import logging
from typing import Union, Optional, Dict, Any, List, Tuple

import numpy as np
from gensim.models import KeyedVectors
from tensorflow import keras

import kashgari.macros as k
from kashgari import utils
from kashgari.embeddings.base_embedding import Embedding
from kashgari.pre_processors.base_processor import BaseProcessor

L = keras.layers


class WordEmbedding(Embedding):
    """Pre-trained word2vec embedding"""

    def __init__(self,
                 w2v_path: str,
                 task: k.TaskType = None,
                 w2v_kwargs: Dict[str, Any] = None,
                 sequence_length: Union[Tuple[int, ...], str, int] = 'auto',
                 processor: Optional[BaseProcessor] = None,
                 **kwargs):
        """

        Args:
            task:
            w2v_path: word2vec file path
            w2v_kwargs: params pass to the ``load_word2vec_format()`` function of ``gensim.models.KeyedVectors`` -
                https://radimrehurek.com/gensim/models/keyedvectors.html#module-gensim.models.keyedvectors
            sequence_length: ``'auto'``, ``'variable'`` or integer. When using ``'auto'``, use the 95% of corpus length
                as sequence length. When using ``'variable'``, model input shape will set to None, which can handle
                various length of input, it will use the length of max sequence in every batch for sequence length.
                If using an integer, let's say ``50``, the input output sequence length will set to 50.
            processor:
            **kwargs:
        """
        if w2v_kwargs is None:
            w2v_kwargs = {}
        self.w2v_path = w2v_path
        self.w2v_kwargs = w2v_kwargs
        self.w2v_model_loaded = False

        super(WordEmbedding, self).__init__(task=task,
                                            sequence_length=sequence_length,
                                            embedding_size=0,
                                            processor=processor)
        if processor:
            self._build_token2idx_from_w2v()
            self._build_model()

    def _build_token2idx_from_w2v(self):
        w2v = KeyedVectors.load_word2vec_format(self.w2v_path, **self.w2v_kwargs)

        token2idx = {
            self.processor.token_pad: 0,
            self.processor.token_unk: 1,
            self.processor.token_bos: 2,
            self.processor.token_eos: 3
        }

        for token in w2v.index2word:
            token2idx[token] = len(token2idx)

        vector_matrix = np.zeros((len(token2idx), w2v.vector_size))
        vector_matrix[1] = np.random.rand(w2v.vector_size)
        vector_matrix[4:] = w2v.vectors

        self.embedding_size = w2v.vector_size
        self.w2v_vector_matrix = vector_matrix
        self.w2v_token2idx = token2idx
        self.w2v_top_words = w2v.index2entity[:50]
        self.w2v_model_loaded = True

        self.processor.token2idx = self.w2v_token2idx
        self.processor.idx2token = dict([(value, key) for key, value in self.w2v_token2idx.items()])
        logging.debug('------------------------------------------------')
        logging.debug('Loaded gensim word2vec model')
        logging.debug('model        : {}'.format(self.w2v_path))
        logging.debug('word count   : {}'.format(len(self.w2v_vector_matrix)))
        logging.debug('Top 50 word  : {}'.format(self.w2v_top_words))
        logging.debug('------------------------------------------------')

    def _build_model(self, **kwargs):
        if self.token_count == 0:
            logging.debug('need to build after build_word2idx')
        else:
            input_layers = []
            output_layers = []
            for index, seq_len in enumerate(self.sequence_length):
                input_tensor = L.Input(shape=(seq_len,),
                                       name=f'input_{index}')
                layer_embedding = L.Embedding(self.token_count,
                                              self.embedding_size,
                                              weights=[self.w2v_vector_matrix],
                                              trainable=False,
                                              name=f'layer_embedding_{index}')

                embedded_tensor = layer_embedding(input_tensor)

                input_layers.append(input_tensor)
                output_layers.append(embedded_tensor)
            if len(output_layers) > 1:
                layer_concatenate = L.Concatenate(name='layer_concatenate')
                output = layer_concatenate(output_layers)
            else:
                output = output_layers

            self.embed_model = keras.Model(input_layers, output)

    def analyze_corpus(self,
                       x: Union[Tuple[List[List[str]], ...], List[List[str]]],
                       y: Union[List[List[Any]], List[Any]]):
        """
        Prepare embedding layer and pre-processor for labeling task

        Args:
            x:
            y:

        Returns:

        """
        x = utils.wrap_as_tuple(x)
        y = utils.wrap_as_tuple(y)
        if not self.w2v_model_loaded:
            self._build_token2idx_from_w2v()

        super(WordEmbedding, self).analyze_corpus(x, y)


if __name__ == "__main__":
    from kashgari.corpus import SMP2018ECDTCorpus
    import kashgari
    import os

    logging.basicConfig(level=logging.DEBUG)

    train_x, train_y = SMP2018ECDTCorpus.load_data()

    w2v_path = os.path.join(kashgari.utils.get_project_path(), 'tests/test-data/sample_w2v.txt')

    embedding = WordEmbedding(task=kashgari.CLASSIFICATION,
                              w2v_path=w2v_path,
                              sequence_length=(12, 20))
    embedding.analyze_corpus((train_x, train_x), train_y)
    embedding._build_model()
    embedding.embed_model.summary()
    r = embedding.embed((train_x[:2], train_x[:2]))
    print(r)
    print(r.shape)
