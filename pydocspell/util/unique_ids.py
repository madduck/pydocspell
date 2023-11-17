import random
from base58 import b58encode
import itertools

def make_unique_id(*, seed=None, bytes=32, seglen=11, sep='-'):
    generator = random.Random(seed)
    b58 = b58encode(generator.randbytes(bytes)).decode('utf8')

    def batched(string, n):
        while batch := string[0:n]:
            yield batch
            string = string[n:]

    return sep.join(batched(b58, seglen))
