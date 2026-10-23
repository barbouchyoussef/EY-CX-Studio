"""Consolidates findings from every module into one prioritised issue log.

The only module that reads the output of the others, which is why it defines a shared finding
contract and one extractor per source type.
"""
