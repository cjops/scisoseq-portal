import { nodeResolve } from '@rollup/plugin-node-resolve';
import { terser } from "rollup-plugin-terser";
import copy from 'rollup-plugin-copy'

export default {
    input: 'gtex-viz/src/TranscriptBrowser2.js',
    output: {
        file: 'static/js/transcript-browser.bundle.min.js',
        format: 'iife',
        sourcemap: 'inline',
        name: 'TranscriptBrowser'    
    },
    plugins: [
        nodeResolve(),
        terser(),
        copy({
            targets: [
                { src: ['gtex-viz/css/isoform.css'], dest: 'static/css' }
            ],
            verbose: true
        })
    ]
};