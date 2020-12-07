import sqlite3
import json
from pathlib import Path
from pprint import pprint

_con = sqlite3.connect('scisoseq.db')
#_con.row_factory = sqlite3.Row

def create_tables():
    _con.executescript("""
    CREATE TABLE IF NOT EXISTS datasets (
        name TEXT NOT NULL PRIMARY KEY,
        date TEXT
    );
    CREATE TABLE IF NOT EXISTS genes (
        chromosome TEXT,
        source TEXT,
        feature_type TEXT,
        start INT,
        end INT,
        score TEXT,
        strand TEXT,
        frame TEXT,
        attributes TEXT,
        dataset TEXT REFERENCES datasets,
        gene_id TEXT NOT NULL,
        gene_name TEXT,
        PRIMARY KEY(gene_id, dataset)
    );
    CREATE TABLE IF NOT EXISTS transcripts (
        chromosome TEXT,
        source TEXT,
        feature_type TEXT,
        start INT,
        end INT,
        score TEXT,
        strand TEXT,
        frame TEXT,
        attributes TEXT,
        dataset TEXT REFERENCES datasets,
        gene_id TEXT,
        gene_name TEXT,
        transcript_id TEXT NOT NULL,
        FOREIGN KEY(gene_id, dataset) REFERENCES genes(gene_id, dataset),
        PRIMARY KEY(transcript_id, gene_id, dataset)
    );
    CREATE TABLE IF NOT EXISTS exons (
        chromosome TEXT,
        source TEXT,
        feature_type TEXT,
        start INT,
        end INT,
        score TEXT,
        strand TEXT,
        frame TEXT,
        attributes TEXT,
        dataset TEXT REFERENCES datasets,
        gene_id TEXT,
        gene_name TEXT,
        transcript_id TEXT,
        exon_id TEXT,
        exon_number INT NOT NULL,
        FOREIGN KEY(gene_id, dataset) REFERENCES genes(gene_id, dataset),
        FOREIGN KEY(transcript_id, gene_id, dataset) REFERENCES transcripts(transcript_id, gene_id, dataset)
        PRIMARY KEY(transcript_id, exon_number, gene_id, dataset)
    );
    CREATE TABLE IF NOT EXISTS model_exons (
        chromosome TEXT,
        start INT,
        end INT,
        strand TEXT,
        gene_name TEXT NOT NULL,
        exon_id TEXT,
        exon_number INT NOT NULL,
        PRIMARY KEY(gene_name, exon_number)
    )
    """)

def create_indices():
    _con.executescript("""
    CREATE INDEX index_genes_gene_name ON genes(gene_name);
    CREATE INDEX index_transcripts_gene_name ON transcripts(gene_name);
    CREATE INDEX index_exons_gene_name ON exons(gene_name);
    CREATE INDEX index_model_exons_gene_name ON model_exons(gene_name);
    """)

def parse_gtf_attr(s):
    d = {}
    for item in s.split(';')[:-1]:
        item = item.strip().split(' ', maxsplit=1)
        if item[0] in d:
            d[item[0]].append(item[1].strip('"'))
        else:
            d[item[0]] = [item[1].strip('"')]
    return {k: v if len(v) > 1 else v[0] for k,v in d.items()}

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
        'frame': cols[7],
        'attributes': parse_gtf_attr(cols[8])
    }
    return feature

def remove_ensembl_suffix(id):
    if id.startswith('ENS'):
        return id.rsplit('.', maxsplit=1)[0]
    else:
        return id

def import_gtf(f, name):
    if _con.execute('SELECT * FROM datasets WHERE name=?', (name,)).fetchone():
        print('\tGTF already imported')
        return
    gene_count = 0
    tx_count = 0
    ex_count = 0
    with _con:
        _con.execute('INSERT INTO datasets VALUES (?, ?)', (name, date.today()))
        for line in f:
            if line[0] == '#': continue
            feat = parse_gtf_line(line)
            try:
                if feat['feature_type'] == 'gene':
                    _con.execute('INSERT INTO genes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                        *list(feat.values())[:8],
                        json.dumps(feat['attributes']),
                        name,
                        feat['attributes']['gene_id'],
                        feat['attributes'].get('gene_name')
                    ))
                    gene_count += 1
                elif feat['feature_type'] == 'transcript':
                    _con.execute('INSERT INTO transcripts VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                        *list(feat.values())[:8],
                        json.dumps(feat['attributes']),
                        name,
                        feat['attributes']['gene_id'],
                        feat['attributes'].get('gene_name'),
                        feat['attributes']['transcript_id']
                    ))
                    tx_count += 1
                    if tx_count % 1000 == 0:
                        print('\tread', tx_count, 'transcripts from file')
                elif feat['feature_type'] == 'exon':
                    _con.execute('INSERT INTO exons VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (
                        *list(feat.values())[:8],
                        json.dumps(feat['attributes']),
                        name,
                        feat['attributes']['gene_id'],
                        feat['attributes'].get('gene_name'),
                        feat['attributes']['transcript_id'],
                        feat['attributes'].get('exon_id'),
                        feat['attributes']['exon_number']
                    ))
                    ex_count += 1
            except sqlite3.IntegrityError:
                pprint(feat)
                raise
    print(f'\tinserted {gene_count} genes/{tx_count} transcripts/{ex_count} exons into db')

def drop_dataset(name):
    with _con:
        _con.execute('DELETE FROM exons WHERE dataset=?', (name,))
        _con.execute('DELETE FROM transcripts WHERE dataset=?', (name,))
        _con.execute('DELETE FROM genes WHERE dataset=?', (name,))
        _con.execute('DELETE FROM datasets WHERE name=?', (name,))

def drop_model_exons():
    with _con:
        _con.execute('DELETE FROM model_exons')
drop_model_exons()

def generate_selectize(f, dataset):
    selectize = sorted([x[0] for x in _con.execute('SELECT DISTINCT gene_name FROM genes WHERE dataset=?', (dataset,))])
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

def generate_model_exons(dataset):
    genes = [x[0] for x in _con.execute('SELECT DISTINCT gene_name FROM genes WHERE dataset=?', (dataset,))]
    print('Found', len(genes), 'distinct genes in', dataset)
    gene_count = 0
    ex_count = 0
    with _con:
        for gene in genes:
            chrom = None
            strand = None
            exon_coords = []
            rows = _con.execute("""SELECT
                chromosome,
                start,
                end,
                strand,
                json_extract(attributes, '$.transcript_type')
            FROM exons WHERE gene_name=?""", (gene,))
            for row in rows:
                if not chrom:
                    chrom = row[0]
                if not strand:
                    chrom = row[3]
                if row[4] == 'retained_intron':
                    continue
                exon_coords.append([row[1], row[2]])
                ex_count += 1
            new_coords = interval_union(exon_coords)
            #start_pos = np.min([i[0] for i in new_coords])
            #end_pos = np.max([i[1] for i in new_coords])
            if strand == '-':
                new_coords.reverse()
            for i, (start, end) in enumerate(new_coords, 1):
                _con.execute('INSERT INTO model_exons VALUES (?, ?, ?, ?, ?, ?, ?)', (
                    chrom,
                    start,
                    end,
                    strand,
                    gene,
                    '_'.join([gene, str(i)]),
                    i
                ))
            gene_count += 1
            if gene_count % 1000 == 0:
                print('Processed', gene_count, 'genes')
    print('Generated', ex_count, 'exons across', gene_count, 'genes')

def import_expression_values(f, dataset):
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
    with _con:
        for tx_id in tx:
            exp = [dict(zip(['cell_type', 'avg_exp', 'pct_exp', 'avg_exp_scaled'], [k]+v)) for k,v in tx[tx_id].items()]
            cur = _con.execute("UPDATE transcripts SET attributes=(SELECT json_set(attributes, '$.expression', json('"+json.dumps(exp)+"')) FROM transcripts) WHERE transcript_id=? AND dataset=?", (tx_id, dataset))
            write_count += cur.rowcount
            if cur.rowcount > 0 and write_count % 1000 == 0:
                print('wrote', write_count, 'transcripts to db')
    if write_count % 1000 != 0:
        print('wrote', write_count, 'transcripts to db')
