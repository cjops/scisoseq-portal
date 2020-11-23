import json
import pymongo
#sys.path.append("gtex-pipeline/gene_model")
#from collapse_annotation import collapse_annotation, Annotation

from pymongo import MongoClient
_client = MongoClient('localhost', 27017)
_db = _client.gandallab

from pymongo import InsertOne
from pymongo.errors import BulkWriteError
from pprint import pprint

def attr_str_to_dict(s):
    d = {}
    for item in s.split(';')[:-1]:
        item = item.strip().split(' ', maxsplit=1)
        d[item[0]] = item[1].strip('"')
    return d

def parse_gtf_line(line):
    line = line.rstrip()
    cols = line.split('\t')
    feature = {
        'chromosome': cols[0],
        'source': cols[1],
        'feature_type': cols[2],
        'start': int(cols[3]),
        'end': int(cols[4]),
        'score': cols[5],
        'strand': cols[6],
        'frame': cols[7]
    }
    feature.update(attr_str_to_dict(cols[8]))
    return feature

def mongo_bulk_write_genes(ops, count=0):
    try:
        _db.genes.bulk_write(ops, ordered=False)
    except BulkWriteError as bwe:
        pprint(bwe.details)
    print('\twrote', count+len(ops), 'genes to db')
    return len(ops)

def mongo_insert_gtf(f, name):
    if _db.genes.find_one({'file': name}, {}):
        print('\tGTF already inserted')
        return
    
    tx_count = 0
    gene_count = 0
    ops = []
    current_gene = None

    for line in f:
        if line[0] == '#': continue

        feat = parse_gtf_line(line)

        if feat['feature_type'] == 'gene':
            if current_gene:
                ops.append(InsertOne({
                    'file': name,
                    'gene_id_short': current_gene['gene_id'].rsplit('.', maxsplit=1)[0],
                    'gene': current_gene
                }))
            current_gene = feat
            current_gene['transcripts'] = []
        elif feat['feature_type'] == 'transcript':
            current_gene['transcripts'].append(feat)
            current_gene['transcripts'][-1]['exons'] = []
            tx_count += 1
            if tx_count % 1000 == 0:
                print('\tread', tx_count, 'transcripts from file')
        elif feat['feature_type'] == 'exon':
            current_gene['transcripts'][-1]['exons'].append(feat)
        
        if len(ops) >= 1000:
            gene_count += mongo_bulk_write_genes(ops, gene_count)
            ops = []
    
    if tx_count % 1000 != 0:
        print('\tread', tx_count, 'transcripts from file')
    if current_gene:
        ops.append(InsertOne({
            'file': name,
            'gene_id_short': current_gene['gene_id'].rsplit('.', maxsplit=1)[0],
            'gene': current_gene
        }))
    if ops:
        mongo_bulk_write_genes(ops, gene_count)

def generate_selectize(f, gene_file=None):
    filter = {'file': gene_file} if gene_file else {}
    selectize = sorted(_db.genes.distinct('gene.gene_name', filter))
    f.write('function getSelectizeOptions(){ return ')
    json.dump([{'v': x} for x in selectize], f)
    f.write('; }')
    if hasattr(f, 'name'):
        print('Wrote', len(selectize), 'gene symbols to', f.name)

def interval_union(intervals):
    """
    Returns the union of all intervals in the input list
      intervals: list of tuples or 2-element lists
    """
    intervals.sort(key=lambda x: x[0])
    union = [intervals[0]]
    for i in intervals[1:]:
        if i[0] <= union[-1][1]:  # overlap w/ previous
            if i[1] > union[-1][1]:  # only extend if larger
                union[-1][1] = i[1]
        else:
            union.append(i)
    return union

def mongo_bulk_write_model(ops, count=0):
    try:
        _db.model_exons.bulk_write(ops, ordered=False)
    except BulkWriteError as bwe:
        pprint(bwe.details)
    print('\twrote', count+len(ops), 'genes to db')
    return len(ops)

def mongo_collapse_transcripts(file1, files2=[]):
    genes = _db.genes.distinct('gene.gene_name', {'file': file1})
    filter = {'file': {'$in': files2}} if files2 else {}
    print(len(genes))
    ops = []
    count = 0
    for gene in genes:
        exon_coords = []
        model = []
        results = list(_db.genes.find(
            {'gene.gene_name': gene, **filter},
            {'gene.chromosome': 1, 'gene.strand': 1, 'gene.transcripts.transcript_type': 1, 'gene.transcripts.exons.start': 1, 'gene.transcripts.exons.end': 1}
        ))
        chrom = results[0]['gene']['chromosome']
        strand = results[0]['gene']['strand']
        for document in results:
            for transcript in document['gene']['transcripts']:
                if transcript.get('transcript_type') == 'retained_intron':
                    continue
                for exon in transcript['exons']:
                    exon_coords.append([exon['start'], exon['end']])
        new_coords = interval_union(exon_coords)
        #start_pos = np.min([i[0] for i in new_coords])
        #end_pos = np.max([i[1] for i in new_coords])
        if strand == '-':
            new_coords.reverse()
        for i, (start, end) in enumerate(new_coords, 1):
            model.append({
                'chromosome': chrom,
                'strand': strand,
                'start': start,
                'end': end,
                'exon_id': '_'.join([gene, str(i)]),
                'exon_number': i
            })
        ops.append(InsertOne({
            'gene_name': gene,
            'exons': model
        }))
        if len(ops) >= 1000:
            count += mongo_bulk_write_model(ops, count)
            ops = []
    if ops:
        mongo_bulk_write_model(ops, count)

def mongo_add_expression(f, gene_file):
    tx = {}
    for i,line in enumerate(f):
        if i == 0:
            continue
        tokens = line.split()
        tx_id = tokens[3].replace('-', '_')
        cell_type = tokens[4]
        avg_exp = float(tokens[1])
        pct_exp = float(tokens[2])
        avg_exp_scaled = float(tokens[5])
        if tx_id not in tx:
            tx[tx_id] = {}
        tx[tx_id][cell_type] = [avg_exp, pct_exp, avg_exp_scaled]
    print(len(tx), 'total transcripts')
    write_count = 0
    other_count = 0
    no_match_count = 0
    for tx_id in tx:
        exp = [dict(zip(['cell_type', 'avg_exp', 'pct_exp', 'avg_exp_scaled'], [k]+v)) for k,v in tx[tx_id].items()]
        db_results = {x['file']: x['_id'] for x in _db.genes.find({'gene.transcripts.transcript_id': tx_id}, {'file': 1})}
        if gene_file in db_results:
            _db.genes.update_one(
                {'_id': db_results[gene_file], 'gene.transcripts.transcript_id': tx_id},
                {'$set': {'gene.transcripts.$.expression': exp}}
            )
            write_count += 1
        elif len(db_results) > 0:
            other_count += 1
        else:
            no_match_count += 1
        if write_count % 1000 == 0:
            print('wrote', write_count, 'transcripts to db')
    if write_count % 1000 != 0:
        print('wrote', write_count, 'transcripts to db')
    if other_count > 0:
        print(other_count, 'transcripts in db but not under', gene_file)
    if no_match_count > 0:
        print(no_match_count, 'transcripts not found in db')
