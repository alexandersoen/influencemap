'''
Functions for querying MAG API to get paper information fields.
Aimed to provide caching in ES.

date:   25.06.18
author: Alexander Soen
'''

from core.config import *
from core.search.mag_interface import *
from core.search.query_info_db import papers_prop_query
from core.search.parse_academic_search import or_query_builder_list

MAS_URL_PREFIX = "https://api.labs.cognitive.microsoft.com"

basic_attr = {'Id': 'PaperId',
              'Y' : 'Year'}

compound_attr = {
             'C': {
                'CId': 'ConferenceSeriesId',
                'CN' : 'ConferenceName',
                },
             'J': {
                'JId': 'JournalId',
                'JN' : 'JournalName',
                },
             'AA': {
                'AuId': 'AuthorId',
                'AuN' : 'AuthorName',
                'AfId': 'AffiliationId',
                'AfN' : 'AffiliationName',
                },
             'F': {
                'FId': 'FieldOfStudyId',
                'FN' : 'FieldOfStudyName',
                }
             }

list_attr_names = {'AA': 'Authors',
                   'F' : 'FieldOfStudy'}

# Create search
compound_snames = list(basic_attr.keys())
for attr_type, attr in compound_attr.items():
    # Create name to search
    to_name = lambda x: '.'.join([attr_type, x])
    compound_snames += list(map(to_name, attr.keys()))
# Turn into string
compound_snames = ','.join(compound_snames)


def base_paper_mag_multiquery(paper_ids):
    ''' Returns all basic fields of a paper with API.
    '''
    url = os.path.join(MAS_URL_PREFIX, "academic/v1.0/evaluate")
    queries = ({
        'expr': expr,
        'count': 10000,
        'offset': 0,
        'attributes': compound_snames
        } for expr in or_query_builder_list('Id={}', paper_ids))

    # Query result
    results = dict()

    for query in queries:
        data = query_academic_search('get', url, query)
        for res in data['entities']:
            res_row = dict()

            # Get basic attributes
            for a, n in basic_attr.items():
                if a in res:
                    res_row[n] = res[a]

            # Get compound attributes
            for t, ca in compound_attr.items():
                # Check if result exists for type
                if t not in res:
                    continue

                # If field type, need to process list
                if t in list_attr_names.keys():
                    attr_res = list()

                    # Go through each value in list
                    for a_dict in res[t]:
                        suba_dict = dict()
                        # Get values for single entry
                        for a, n in ca.items():
                            if a in a_dict:
                                suba_dict[n] = a_dict[a]

                        attr_res.append(suba_dict)

                    # Add field
                    res_row[list_attr_names[t]] = attr_res

                # Other singular types
                else:
                    for a, n in ca.items():
                        try:
                            res_row[n] = res[t][a]
                        except KeyError:
                            pass

            # Add paper
            results[res['Id']] = res_row

    # Return results
    return results


def pr_links_mag_multiquery(paper_ids):
    ''' Get the citation links for a paper in paper information format.
    '''
    # Query results
    results = dict()

    # Initalise results
    for paper_id in paper_ids:
        results[paper_id] = {'References': list(), 'Citations': list()}

    # Calculate references
    url = os.path.join(MAS_URL_PREFIX, "academic/v1.0/evaluate")
    queries = ({
        'expr': expr,
        'count': 100000,
        'offset': 0,
        'attributes': 'RId'
        } for expr in or_query_builder_list('Id={}', paper_ids))

    for query in queries:
        data = query_academic_search('get', url, query)

        # Add references
        for res in data['entities']:
            if 'RId' in res:
                results[res['Id']]['References'] += res['RId']

    for paper_id in paper_ids:
        # Checking offsets
        finished = False
        count    = 0

        while not finished:
            query = lambda x: {
            'expr': 'RId={}'.format(paper_id),
            'count': 10000,
            'offset': x,
            'attributes': 'Id,RId'
            }

            data = query_academic_search('get', url, query(count))

            print(count, len(data['entities']))
            if len(data['entities']) > 0:
                count += len(data['entities'])
            else:
                finished = True

            # Add citations
            for res in data['entities']:
                if 'RId' in res:
                    for rid in res['RId']:
                        if rid in paper_ids:
                            results[rid]['Citations'].append(res['Id'])

    return results


def paper_info_mag_multiquery(paper_ids):
    ''' Find paper information with MAG, "optimised"
    '''
    # Get paper links
    paper_links = pr_links_mag_multiquery(paper_ids)

    # Get all papers relevent to this query
    all_papers = list() + paper_ids
    for paper_link in paper_links.values():
        all_papers += paper_link['References'] + paper_link['Citations']

    all_papers = list(set(all_papers))

    # Find all basic properties of all the papers
    paper_props = base_paper_mag_multiquery(all_papers)

    # Add properties to links
    paper_prop_links = dict()
    for paper_id, links in paper_links.items():
        link_res = dict()

        # For each type of link
        for link_type, link_papers in links.items():
            link_type_res = list()

            # Iterate through the link papers to get properties
            for link_paper in link_papers:
                if link_paper in paper_props:
                    link_type_res.append(paper_props[link_paper])

            # Add result of link type
            link_res[link_type] = link_type_res

        # Add to updated links
        paper_prop_links[paper_id] = link_res

    # Turn into paper_info dictionaries
    paper_info_res = list()
    
    for paper_id in paper_ids:
        try:
            # Combine queries
            paper_prop = paper_props[paper_id]
            paper_link = paper_prop_links[paper_id]
            paper_info_res.append(dict(paper_prop, **paper_link))
        except KeyError:
            pass

    return paper_info_res


if __name__ == '__main__':
    # TEST
    from query_paper_mag import author_paper_mag_query
#    print(paa_prop_multiquery([2279671314]))
    #print(pr_links_mag_multiquery([2279671314]))
    #base_paper_mag_multiquery_test([2010977797, 2279671314, 2059658980])
    papers = author_paper_mag_query(2100918400)
    paper_info = paper_info_mag_multiquery(papers)
    print(paper_info)
    #print(paa_prop_mag_multiquery([2010977797]))
