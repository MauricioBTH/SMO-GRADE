/**
 * Gera imagens PNG de todos os cards visiveis e faz download.
 */
async function gerarImagens() {
  var cards = document.querySelectorAll('#cards-container .card');
  if (cards.length === 0) return;

  var btn = document.getElementById('btn-gerar');
  var bar = document.getElementById('progress-bar');
  var fill = document.getElementById('progress-fill');

  btn.disabled = true;
  document.getElementById('btn-gerar-text').textContent = 'Gerando...';
  bar.style.display = 'block';

  for (var i = 0; i < cards.length; i++) {
    var card = cards[i];
    var cardTitle = card.getAttribute('data-card-title') || 'card';
    var cardUnidade = card.getAttribute('data-card-unidade') || '';
    var numero = String(i + 1).padStart(2, '0');
    var unidadeSlug = cardUnidade.replace(/[^a-zA-Z0-9]/g, '');
    var tituloSlug = cardTitle.normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^a-zA-Z0-9 ]/g, '')
      .replace(/\s+/g, '_');
    var nomeArquivo = unidadeSlug + '_' + numero + '_' + tituloSlug + '.png';

    try {
      var canvas = await html2canvas(card, {
        scale: 3,
        useCORS: true,
        backgroundColor: '#ffffff',
        logging: false,
      });

      var link = document.createElement('a');
      link.download = nomeArquivo;
      link.href = canvas.toDataURL('image/png');
      link.click();
    } catch (err) {
      console.error('Erro ao gerar card ' + nomeArquivo, err);
    }

    var pct = Math.round(((i + 1) / cards.length) * 100);
    fill.style.width = pct + '%';

    await new Promise(function (r) { setTimeout(r, 300); });
  }

  btn.disabled = false;
  document.getElementById('btn-gerar-text').textContent = 'Gerar Cards';
  bar.style.display = 'none';
  fill.style.width = '0%';
}
