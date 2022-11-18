#!/bin/bash

#runs input through ast twice. both outputs should match
cat test_1 | python3 dump_tree.py | tee >(cat - >&2) | python3 dump_tree.py stats

#test 2 is test 1 without structs, enums, and unions
cat test_2 | python3 dump_tree.py | tee >(cat - >&2) | python3 dump_tree.py stats

#test 3 is for forward types
cat test_3 | python3 dump_tree.py | tee >(cat - >&2) | python3 dump_tree.py stats
