"""Focused checks for experimental ranking. (done by codex)"""
import unittest
from compare_bm25_hybrid import BM25, tokens

class RankingChecks(unittest.TestCase):
    def test_whole_identifiers_do_not_match_inside_words(self):
        index = BM25([{'body':'abcdefg basic reach'}, {'body':'ABC ABD EFG'}])
        self.assertEqual(index.search('ABC'), [1])

    def test_short_identifiers_and_accented_words_survive(self):
        self.assertEqual(tokens('Step 4 QA Caf\u00e9'), ['step','4','qa','caf\u00e9'])

    def test_rare_identifier_beats_repeated_common_term(self):
        index = BM25([{'body':'error '*100}, {'body':'error 53300'}, {'body':'error network'}])
        self.assertEqual(index.search('error 53300')[0], 1)

    def test_empty_query_and_empty_corpus(self):
        self.assertEqual(BM25([]).search('hello'), [])
        self.assertEqual(BM25([{'body':'hello'}]).search(''), [])

if __name__ == '__main__':
    unittest.main()
