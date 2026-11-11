/* Pulsanti «Copia prompt» delle verifiche. Derivato da istruttoria-coordinamento/assets/copia-prompt.js
   (una sola area per pagina) e generalizzato a piu' prompt: ogni pulsante copia il <pre class="prompt"> del suo riquadro. */
(function(){
  document.querySelectorAll('button.copia').forEach(function(b){
    b.addEventListener('click', function(){
      var t = b.parentNode.querySelector('pre.prompt').textContent;
      function flash(m){ b.textContent = m; b.classList.add('done');
        setTimeout(function(){ b.textContent = 'Copia prompt'; b.classList.remove('done'); }, 1800); }
      function legacy(){
        var ta = document.createElement('textarea');
        ta.value = t; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        var ok = false; try { ok = document.execCommand('copy'); } catch (e) {}
        document.body.removeChild(ta);
        flash(ok ? 'Copiato' : 'Copia a mano (Ctrl/Cmd+C)');
      }
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(t).then(function(){ flash('Copiato'); }, legacy);
      } else { legacy(); }
    });
  });
})();
