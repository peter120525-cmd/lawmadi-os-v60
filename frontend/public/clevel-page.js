// Smooth scroll reveal animation
var observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

var observer = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

document.querySelectorAll('.executive-card').forEach(function(card) {
    card.style.opacity = '0';
    card.style.transform = 'translateY(30px)';
    observer.observe(card);
});

// Hover effect on avatar
document.querySelectorAll('.executive-avatar').forEach(function(avatar) {
    avatar.addEventListener('mouseenter', function() {
        this.style.transform = 'scale(1.05)';
        this.style.boxShadow = '0 25px 50px rgba(0, 0, 0, 0.4)';
    });

    avatar.addEventListener('mouseleave', function() {
        this.style.transform = 'scale(1)';
        this.style.boxShadow = '0 20px 40px rgba(0, 0, 0, 0.3)';
    });
});

// Page load animation
window.addEventListener('load', function() {
    document.body.style.opacity = '0';
    setTimeout(function() {
        document.body.style.transition = 'opacity 0.5s';
        document.body.style.opacity = '1';
    }, 100);
});


// Disable right-click context menu
document.addEventListener('contextmenu', function(e) { e.preventDefault(); });
