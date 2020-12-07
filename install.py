import sys
from pathlib import Path
from util import *

data_dir = Path(sys.argv[1])
primary_dataset = sys.argv[2]

print('1/5 creating tables')

create_tables()
create_indices()

print('2/5 importing GTFs')

for gtf in data_dir.glob('*.gtf'):
    print('Processing', gtf.name)
    with open(gtf) as f:
        import_gtf(f, gtf.stem)

print('\n\n3/5 building gene models')

generate_model_exons(primary_dataset)

print('\n\n4/5 writing list of gene symbols for selectize')

with open('static/js/all_symbols.js', 'w') as f:
    generate_selectize(f, primary_dataset)

print('\n\n5/5 adding expression values')
for exp in data_dir.glob('*expression.txt'):
    print('Processing', exp.name)
    with open(exp) as f:
        import_expression_values(f, primary_dataset)
