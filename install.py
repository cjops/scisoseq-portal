import sys
from pathlib import Path
from util import *

data_dir = Path(sys.argv[1])
gene_file = sys.argv[2]

print('1/5 importing GTFs')

for gtf in data_dir.glob('*.gtf'):
    print('Processing', gtf.name)
    with open(gtf) as f:
        mongo_insert_gtf(f, gtf.stem)

print('\n\n2/5 building gene models')

mongo_collapse_transcripts(gene_file)

print('\n\n3/5 setting indexes')

_db.genes.create_index([('file', pymongo.ASCENDING), ('gene.gene_name', pymongo.ASCENDING)])
_db.genes.create_index([('file', pymongo.ASCENDING), ('gene_id_short', pymongo.ASCENDING)])
_db.genes.create_index('gene.gene_name')
_db.genes.create_index('gene_id_short')
_db.genes.create_index('gene.transcripts.transcript_id')

_db.model_exons.create_index('gene_name', unique=True)

print('\n\n4/5 writing list of gene symbols for selectize')

with open('static/js/all_symbols.js', 'w') as f:
    generate_selectize(f, gene_file)

print('\n\n5/5 adding expression values')
for exp in data_dir.glob('*expression.txt'):
    print('Processing', exp.name)
    with open(exp) as f:
        mongo_add_expression(f, gene_file)
