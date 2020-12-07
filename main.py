from flask import Flask, request, render_template
from flask_cors import CORS
app = Flask(__name__, static_url_path='')
CORS(app)

import sqlite3
import json
import time

def find_gene(gene_name, gene_files=[]):
    tic = time.time()
    _con = sqlite3.connect('scisoseq.db')
    #_con.row_factory = sqlite3.Row
    txd = []
    exd = {}
    model = []
    #filter = {'file': {'$in': gene_files}} if gene_files else {}
    transcripts = _con.execute("""SELECT
        json_extract(attributes, '$.transcript_type'),
        chromosome,
        start,
        end,
        strand,
        dataset,
        gene_id,
        gene_name,
        transcript_id,
        json_extract(attributes, '$.expression')
    FROM transcripts WHERE gene_name=?""", (gene_name,))
    for tx in transcripts:
        if tx[0] == 'retained_intron':
            continue
        tx = dict(zip(('chromosome', 'start', 'end', 'strand', 'file', 'gencodeId', 'geneSymbol', 'transcriptId', 'expression'), tx[1:]))
        tx['transcriptId'] = '_'.join([tx['file'], tx['transcriptId']]).replace('.', '_')
        tx['chromosome'] = tx['chromosome'].lstrip('chr')
        if tx['expression']:
            tx['expression'] = json.loads(tx['expression'])
        else:
            tx['expression'] = []
        txd.append(tx)
    exons = _con.execute("""SELECT
        dataset,
        transcript_id,
        chromosome,
        start,
        end,
        strand,
        exon_number
    FROM exons WHERE gene_name=?""", (gene_name,))
    for ex in exons:
        tid = '_'.join([ex[0], ex[1]]).replace('.', '_')
        ex = dict(zip(('chrom', 'chromStart', 'chromEnd', 'strand', 'exonNumber'), ex[2:]))
        if tid not in exd:
            exd[tid] = []
        exd[tid].append(ex)
    model_exons = _con.execute("""SELECT
        chromosome,
        start,
        end,
        strand,
        exon_id,
        exon_number
    FROM model_exons WHERE gene_name=?""", (gene_name,))
    for ex in model_exons:
        ex = dict(zip(('chrom', 'chromStart', 'chromEnd', 'strand', 'exonId', 'exonNumber'), ex))
        model.append(ex)
    toc = time.time()
    print(toc-tic)
    return {'exons': exd, 'transcripts': txd, 'modelExons': model}

@app.route('/')
def hello_world():
    return render_template('index.html')

@app.route("/gene")
def gene_api():
    gene_name = request.args.get('geneId')
    print(gene_name)
    return find_gene(gene_name)