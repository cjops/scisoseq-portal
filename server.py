from flask import Flask, request, render_template
from flask_cors import CORS
app = Flask(__name__, static_url_path='')
CORS(app)

from pymongo import MongoClient
client = MongoClient('localhost', 27017)
db = client.gandallab

def find_gene(gene_name, gene_files=[]):
    txd = []
    exd = {}
    model = []
    filter = {'file': {'$in': gene_files}} if gene_files else {}
    results = db.genes.find({'gene.gene_name': gene_name, **filter})
    for document in results:
        g = document['gene']
        print(g['gene_id'])
        for tx in g['transcripts']:
            if tx.get('transcript_type') == 'retained_intron':
                continue
            tid = '_'.join([document['file'], tx['transcript_id']]).replace('.', '_')
            txd.append({
                'file': document['file'],
                'chromosome': tx['chromosome'].lstrip('chr'),
                'start': tx['start'],
                'end': tx['end'],
                'strand': tx['strand'],
                'gencodeId': tx['gene_id'],
                'geneSymbol': tx['gene_name'],
                'transcriptId': tid,
                'expression': tx.get('expression', [])
            })
            exd[tid] = []
            for ex in tx['exons']:
                exd[tid].append({
                    'chrom': ex['chromosome'].lstrip('chr'),
                    'chromStart': ex['start'],
                    'chromEnd': ex['end'],
                    'exonNumber': ex['exon_number'],
                    'strand': ex['strand']
                })
    for ex in db.model_exons.find_one({'gene_name': gene_name})['exons']:
        model.append({
            'chrom': ex['chromosome'].lstrip('chr'),
            'chromStart': ex['start'],
            'chromEnd': ex['end'],
            'strand': ex['strand'],
            'exonId': ex['exon_id'],
            'exonNumber': ex['exon_number']
        })
    txd.insert(0, {
        'chromosome': model[0]['chrom'],
        'start': model[0]['chromStart'],
        'end': model[-1]['chromEnd'],
        'strand': model[0]['strand'],
        'gencodeId': 'modelGeneID',
        'geneSymbol': 'modelGeneSymbol',
        'transcriptId': 'modelGeneTranscript'
    })
    exd['modelGeneTranscript'] = model.copy()
    return {'exons': exd, 'transcripts': txd, 'modelExons': model}

@app.route('/')
def hello_world():
    return render_template('index.html')

@app.route("/gene")
def gene_api():
    gene_name = request.args.get('geneId')
    print(gene_name)
    return find_gene(gene_name)