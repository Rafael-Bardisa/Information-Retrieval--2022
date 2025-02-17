import math
import os

import numpy as np
from array import array
from collections import defaultdict, Counter
import functools
from nltk.stem import PorterStemmer
import nltk
from nltk.corpus import stopwords

from myapp.search.load_corpus import load_corpus

nltk.download('stopwords')

BASEDIR = '../../'


def remove_punctuation(text):
    """
    Removes the characters:
    !\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~0123456789
    from the text.
    """
    chars_to_remove = "!\"#$%&'()*+,-./:;<=>?@[\]^_`{|}~0123456789"
    tr = str.maketrans("", "", chars_to_remove)
    return text.translate(tr)


# reuse of the function shown in class to transform text into lowercase and erase stop words in queries
def build_terms(line):
    """
    Preprocess the line removing stop words, stemming, transforming in lowercase and return the tokens of the text.
    Argument:
        line -- string (text) to be preprocessed
    Returns:
        line - a list of tokens corresponding to the input text after the preprocessing
    """
    stemmer = PorterStemmer()
    stop_words = set(stopwords.words("english"))
    line = str(line).lower()
    line = remove_punctuation(line)
    line = line.split()  # Tokenize the text to get a list of terms
    line = [x for x in line if x not in stop_words]  # eliminate the stopwords
    line = [stemmer.stem(word) for word in line]  # perform stemming (HINT: use List Comprehension)
    return line


def create_index(tweets):
    """
    Implement the inverted index
    Argument:
        lines -- collection of Wikipedia articles
    Returns:
        index - the inverted index (implemented through a Python dictionary) containing terms as keys and the
        corresponding list of documents where these keys appear in (and the positions) as values.
    """
    index = defaultdict(list)
    title_index = {}  # dictionary to map page titles to page ids

    for tweet in tweets.values():
        tweet_text = tweet.description
        tweet_id = tweet.id  # tweet id
        terms = str(tweet_text).split(" ")  # page_title + page_text
        title_index[tweet_id] = tweet.title  ## we do not need to apply get terms to title
        current_page_index = {}

        for position, term in enumerate(terms):  # terms contains page_title + page_text. Loop over all terms
            try:
                # if the term is already in the index for the current page append the position to the corresponding list
                current_page_index[term][1].append(position)
            except:
                # Add the new term as dict key and initialize the array of positions and add the position
                current_page_index[term] = [tweet_id, array('I', [position])]  # 'I' indicates unsigned int

        # merge the current page index with the main index
        for term_page, posting_page in current_page_index.items():
            index[term_page].append(posting_page)

    return index, title_index


class IndexException(BaseException):
    pass


def query(text, tweet_index=""):
    """
    search for a given text in the tweet collection using the
    inverted index we previously computed
    :param text: the query text
    :param tweet_index: inverted index of the collection, named as such because context of practice
    :return: list of tweet ids containing all (treated) terms in the query
    """
    terms = build_terms(text)  # necessary step since same treatment applied to tweets
    if not tweet_index:
        raise IndexException

    plausible_ids = []
    for query_term in terms:
        # tweet_index[query_term] is list of tweet ids containing query term + position(s) in text
        # using sets is convenient for using reduce
        plausible_ids.append(set(term_pos[0] for term_pos in tweet_index[query_term]))

    # reduce list of sets to intersection of all
    relevant_ids = functools.reduce(lambda a, b: a.intersection(b), plausible_ids) if plausible_ids else []
    return relevant_ids


def tf_idf(term_freq, document_freq, collection_len):
    if term_freq == 0 or document_freq == 0:
        return 0

    return (1 + math.log(term_freq)) * math.log(collection_len / document_freq)


class CollectionError(BaseException):
    pass


def doc_score(doc_id, collection_index="", collection=""):
    """
    vector de scores para el documento dado, es lo que hay que usar para
    la document length

    tremendo usarlo como {doc_id: doc_score(doc_id)} para todos los ids
    :param doc_id: document id que mirar
    :params: se supone que así será más flexible pero los defaults van finos asi que na
    :return: diccionario de terms y pesos, util para normalizar documentos
    """
    result = {}
    if not collection:
        raise CollectionError
    collection_len = len(collection)

    document = str(collection[doc_id]).split(" ")
    term_frequencies = Counter(document)

    for term in document:
        document_freq = len(query(term, tweet_index=collection_index))
        result[term] = tf_idf(term_frequencies[term], document_freq, collection_len)

    return result


def collection_vectors(collection, collection_index=""):
    """
    multi diccionario de documentos, terms y sus valores tf-idf
    """
    document_vectors = {}
    collection = {tweet.id: tweet.description for tweet in collection.values()}

    for doc_id, document in collection.items():
        document_vectors[doc_id] = doc_score(doc_id, collection_index=collection_index, collection=collection)

    return document_vectors


def cosine_score(query_text, collection, collection_index="", lengths=""):
    """
    computes cosine score of all documents in a collection against a query and ranks them
    accordingly
    """
    collection = {tweet.id: tweet.description for tweet in collection.values()}
    collection_len = len(collection)
    scores = {doc_id: 0 for doc_id in collection.keys()}
    query_terms = build_terms(query_text)  # necessary step since same treatment applied to tweets
    query_frequencies = Counter(query_terms)    # dictionary of frequency of each term in the query

    for term in query_terms:
        # query of a term returns the set of documents containing the term
        document_freq = len(query(term, tweet_index=collection_index))
        query_weight = tf_idf(query_frequencies[term], document_freq, collection_len)

        for doc_id, document in collection.items():
            term_frequencies = Counter(str(document).split(" "))
            document_weight = tf_idf(term_frequencies[term], document_freq, collection_len)
            scores[doc_id] = query_weight * document_weight

    scores = {doc_id: score / np.linalg.norm(list(lengths[doc_id].values())) for doc_id, score in scores.items()}
    doc_ids_sorted = sorted(scores, key=scores.get, reverse=True)

    return {doc_id: scores[doc_id] for doc_id in doc_ids_sorted}


def search_in_corpus(query, corpus, index, lengths):
    # TODO 1. create create_tfidf_index

    # TODO 2. apply ranking
    return cosine_score(query, corpus, collection_index=index, lengths=lengths)


if __name__ == '__main__':
    # utils i have from other stuff ive done in the past
    BLUE = "\033[94m"
    RED = "\033[91m"
    WHITE = "\033[0m"
    BOLD = "\033[1m"


    def read(dictionary: dict, color=RED) -> str:
        """
        Reads dictionaries in a clearer way
        :param dictionary: a dictionary to read
        :param color: ANSI color code to highlight dictionary keys
        :return: the string to print
        """
        entry_list = [f"{color}{key}{WHITE}:\t{value:.2f}" for key, value in dictionary.items()]
        return "\n".join(entry_list)


    full_path = os.path.realpath(__file__)
    path, filename = os.path.split(full_path)
    file_path = path + "/tweets-data-who.json"

    # file_path = "../../tweets-data-who.json"
    corpus = load_corpus(file_path)
    corpus_index, _ = create_index(corpus)
    print(read(search_in_corpus("Risk", corpus, corpus_index)))
