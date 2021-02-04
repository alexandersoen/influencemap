import os, sys, json, requests
import itertools
from datetime import datetime
from collections import Counter
from operator import itemgetter
from core.search.academic_search import *

SIZE_OF_FLOWER = 25

def calculate_citation_score(cite_paper_ids, ego_id):
    # print(len([k for k, v in cite_paper_ids.items() if len(v["citations"]) > 0]))
    paper_origin = {}
    paper_ids = []
    for pid in cite_paper_ids:
        paper_ids.extend(cite_paper_ids[pid]["citations"])
        for c in cite_paper_ids[pid]["citations"]:
            if c in paper_origin:
                paper_origin[c].append(pid)
            else:
                paper_origin[c] = [pid]
    # print([k for k, v in paper_origin.items() if len(v) > 10])

    authors = get_authors_from_papers(paper_ids)
    original_paper_set = set(itertools.chain(*paper_origin.values()))
    paper_authors = {k:[] for k in list(original_paper_set)}
    # print(len(paper_authors))
    for ath in authors["Results"]:
        paper = ath[0]["CellID"]
        # print(paper_origin[paper], paper, ath[0]["AuthorIDs"])
        if ego_id not in ath[0]["AuthorIDs"]:   # remove self citation
            # print("true citation:", paper, paper_origin[paper])
            for original_paper in paper_origin[paper]:
                paper_authors[original_paper].extend(ath[0]["AuthorIDs"])
        # else:
        #     print("self citation:", paper, paper_origin[paper])
    # print([(k, len(v)) for k, v in paper_authors.items()])
    # print(paper_authors.keys())

    authors_score = {}
    for pid, authors in paper_authors.items():
        for author in authors:
            score = 1.0/cite_paper_ids[pid]["numauthor"]
            # numref = cite_paper_ids[pid]["numreference"]
            # score /= numref if numref > 0 else 1 # normalize by # of reference
            if author in authors_score:
                authors_score[author] += score
            else:
                authors_score[author] = score
    return authors_score


def calculate_reference_score(paper_ids, ego_id):
    authors = get_authors_from_papers(paper_ids)
    authors_score = {}
    for ath in authors["Results"]:
        try:
            if ego_id not in ath[0]["AuthorIDs"]:   # remove self citation
                for author in ath[0]["AuthorIDs"]:
                    score = 1.0/len(ath[0]["AuthorIDs"])
                    if author in authors_score:
                        authors_score[author] += score
                    else:
                        authors_score[author] = score
        except Exception as e:
            pass
    return authors_score

def generate_flower_score(cite, ref):
    nameset = set(cite.keys())
    nameset.union(ref.keys())
    flower = []

    author_info = get_author_information(list(nameset))
    author_name = {a[0]["CellID"]:a[0]["Name"] for a in author_info["Results"]}
    for k in nameset:
        cite_score = cite[k] if k in cite else 0
        ref_score = ref[k] if k in ref else 0
        node = {
            "name": author_name[k],
            "influenced": ref_score,
            "influencing": cite_score,
            "sum": cite_score + ref_score,
            "ratio": ref_score - cite_score,
        }
        flower.append(node)
    sorted_by_sum = sorted(flower, key=itemgetter("sum"), reverse=True)[:SIZE_OF_FLOWER]
    return sorted(sorted_by_sum, key=itemgetter("ratio"))


def normalise_score(flower):
    sum_norm = [sys.maxsize, 0]
    ratio_norm = [sys.maxsize, 0]
    infl_norm = [sys.maxsize, 0]
    for node in flower:
        sum_norm[0] = min(sum_norm[0], node["sum"])
        sum_norm[1] = max(sum_norm[1], node["sum"])
        ratio_norm[0] = min(ratio_norm[0], node["ratio"])
        ratio_norm[1] = max(ratio_norm[1], node["ratio"])
        infl_norm[0] = min(infl_norm[0], node["influenced"], node["influencing"])
        infl_norm[1] = max(infl_norm[1], node["influenced"], node["influencing"])
    for node in flower:
        node["sumw"] = (node["sum"]-sum_norm[0])/(sum_norm[1]-sum_norm[0])
        node["ratiow"] = (node["ratio"]-ratio_norm[0])/(ratio_norm[1]-ratio_norm[0])
        node["in_nweight"] = (node["influenced"]-infl_norm[0])/(infl_norm[1]-infl_norm[0])
        node["out_nweight"] = (node["influencing"]-infl_norm[0])/(infl_norm[1]-infl_norm[0])
    return flower
