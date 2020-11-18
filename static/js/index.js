$("#selectGene").on("submit", function(event) {
    event.preventDefault();
    $('#spinner').show();
    var geneSymbol = $(this).find('#geneSymbol').val();
    console.log(geneSymbol)
    $("#gtexTranscriptTracks").empty()
    $("#expressionBubbles").empty()
    TranscriptBrowser.getMongoData(geneSymbol, '').then(function(data){
        let config1 = {
            id: 'gtexTranscriptTracks',
            data: data,
            width: 740,
            marginLeft: 110,
            marginRight: 20,
            marginTop: 30,
            marginBottom: 20,
            labelPos: 'left'
        };
        TranscriptBrowser.transcriptTracks(config1);
        let config2 = {
            id: 'expressionBubbles',
            data: data,
            width: 370,
            labelPos: 'left'
        }
        TranscriptBrowser.transcriptBubbles(config2)
        $('#spinner').hide();
    });
});

$('#geneSymbol').selectize({
    mode: 'multi', // undocumented but important to me
    maxItems: 1,
    valueField: 'v',
    labelField: 'v',
    searchField: 'v',
    options: getSelectizeOptions(),
    create: false,
    openOnFocus: false,
    closeAfterSelect: true,
    selectOnTab: true,
    maxOptions: 100
});
