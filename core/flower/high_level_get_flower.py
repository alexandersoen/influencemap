from webapp.graph                  import processdata
from core.flower.draw_flower_test  import draw_flower
from core.utils.get_entity         import entity_from_name
from core.search.query_paper       import paper_query
from core.search.query_paper_mag   import paper_mag_multiquery
from core.search.query_info        import paper_info_check_query, paper_info_mag_check_multiquery
from core.score.agg_paper_info     import score_paper_info_list
from core.score.agg_score          import agg_score_df
from core.score.agg_utils          import get_coauthor_mapping
from core.score.agg_utils          import flag_coauthor
from core.score.agg_filter         import filter_year
from core.flower.flower_bloom_data import score_df_to_graph
from core.utils.get_stats          import get_stats

from datetime    import datetime
from collections import Counter
from operator    import itemgetter

import core.utils.entity_type as ent

flower_leaves = { 'author': [ent.Entity_type.AUTH]
                , 'conf': [ent.Entity_type.CONF, ent.Entity_type.JOUR]
                , 'inst': [ent.Entity_type.AFFI]
    }

str_to_ent = {
        "author": ent.Entity_type.AUTH,
        "conference": ent.Entity_type.CONF,
        "journal": ent.Entity_type.JOUR,
        "institution": ent.Entity_type.AFFI
    }


def gen_entity_score(paper_information, names, self_cite=True):
    ''' Generates the non-aggregated entity scores
    '''
    entity_scores = [None, None, None]
    for i, flower_item in enumerate(flower_leaves.items()):
        name, leaves = flower_item

        # Timer
        time_cur = datetime.now()

        entity_score = score_paper_info_list(paper_information, leaves, self=names)
        entity_score = entity_score[~entity_score['entity_id'].str.lower().isin(
                                          names)]

        if not self_cite:
            entity_score = entity_score[~entity_score['self_cite']]

        entity_scores[i] = entity_score

    return entity_scores

import pandas
pandas.set_option('display.max_columns', None)


def gen_flower_data(score_dfs, flower_name, pub_lower=None, pub_upper=None,
                                            cit_lower=None, cit_upper=None,
                                            coauthors=None,
                                            include_coauthor=True):
    ''' Generates processed data for flowers given a list of score dataframes.
    '''
    flower_score = [None, None, None]
    for i, flower_item in enumerate(flower_leaves.items()):
        name, leaves = flower_item

        time_cur = datetime.now()

        # Filter score dfs first
        print(pub_lower, pub_upper, cit_lower, cit_upper)
        print(score_dfs[i])
        print(score_dfs[i][score_dfs[i]['influence_year'] > cit_lower])
        agg_score = filter_year(score_dfs[i], pub_lower, pub_upper)
        print(agg_score)
        agg_score = filter_year(agg_score, cit_lower, cit_upper,
                                index = 'influence_year')
        print(agg_score)

        # Aggregate
        agg_score = agg_score_df(agg_score)

        # Filter coauthors
        if (include_coauthor == True):
            agg_score = flag_coauthor(agg_score, coauthors)
        else:
            agg_score = agg_score[ ~agg_score['entity_id'].isin(coauthors) ]

        agg_score.ego = flower_name

        print()
        print('Aggregated score for', leaves)
        print('Time taken: ', datetime.now() - time_cur)
        print()

        time_cur = datetime.now()

        score = score_df_to_graph(agg_score)

        print()
        print('Score to graph for', leaves)
        print('Time taken: ', datetime.now() - time_cur)
        print()

        flower_score[i] = score

    author_data = processdata("author", flower_score[0])
    conf_data   = processdata("conf", flower_score[1])
    inst_data   = processdata("inst", flower_score[2])

    return author_data, conf_data, inst_data


def get_flower_data_high_level(entitytype, authorids, normalizedname, selection=None):

    time_cur = datetime.now()

    # Get the selected paper
    selected_papers = list()
    if selection:
        # If selection is not None, they follow selection
        for eid in authorids:
            selected_papers += list(map(lambda x : x['eid'], selection[eid]))
    else:
        selected_papers = paper_mag_multiquery(str_to_ent[entitytype], authorids)

    print()
    print('Number of Papers Found: ', len(selected_papers))
    print('Time taken: ', datetime.now() - time_cur)
    print()

    time_cur = datetime.now()

    # Turn selected paper into information dictionary list
    paper_information = paper_info_mag_check_multiquery(selected_papers) # API

    # Get coauthors
    coauthors = get_coauthor_mapping(paper_information)

    print()
    print('Number of Paper Information Found: ', len(paper_information))
    print('Time taken: ', datetime.now() - time_cur)
    print()
    if not paper_information:
        return None

    # Get min and maximum year
    years = [info['Year'] for info in paper_information if 'Year' in info]
    min_year = min(years)
    max_year = max(years)
    year_counter = sorted(list(Counter(years).items()), key=itemgetter(0))
    year_chart = [["Year", "Num of Papers"]]
    year_chart.extend([[k,v] for k,v in year_counter])
    print(year_chart)

    # Generate score for each type of flower
    entity_scores = gen_entity_score(paper_information, [normalizedname],
                                     self_cite=False)

    # Generate flower data
    author_data, conf_data, inst_data = gen_flower_data(entity_scores,
                                                        normalizedname,
                                                        coauthors = coauthors)

    # Set cache
    cache = {'cache': selected_papers, 'coauthors': coauthors}

    # Set statistics
    stats = get_stats(paper_information)

    data = {
        "author": author_data,
        "conf":   conf_data,
        "inst":   inst_data,
        "yearSlider": {
            "title": "Publications range",
            "range": [min_year, max_year],
            "counter": year_chart
        },
        "stats": stats
    }

    return cache, data