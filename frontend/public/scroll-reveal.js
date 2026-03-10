// Scroll reveal animation (IntersectionObserver)
(function(){
    var io = new IntersectionObserver(function(entries){
        entries.forEach(function(e){ if(e.isIntersecting){ e.target.classList.add('visible'); io.unobserve(e.target); } });
    }, {threshold: 0.1});
    document.querySelectorAll('.article-card, .effective-date, .footer-nav').forEach(function(el){ io.observe(el); });
})();
