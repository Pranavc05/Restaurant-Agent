// Initialize Lucide icons
lucide.createIcons();

// Demo phone number (replace with actual Twilio number)
const DEMO_PHONE_NUMBER = "+1 (989) 402-9906"; // Your actual Twilio number

// Update phone number display
document.addEventListener('DOMContentLoaded', function() {
    const phoneNumberElement = document.querySelector('.phone-number');
    if (phoneNumberElement) {
        phoneNumberElement.textContent = DEMO_PHONE_NUMBER;
    }
});

// Start demo function
function startDemo() {
    // Option 1: Direct call (mobile only)
    if (window.innerWidth <= 768) {
        window.location.href = `tel:${DEMO_PHONE_NUMBER.replace(/\D/g, '')}`;
    } else {
        // Option 2: Show instructions for desktop
        showDemoModal();
    }
}

// Show demo modal for desktop users
function showDemoModal() {
    const modal = document.createElement('div');
    modal.className = 'demo-modal';
    modal.innerHTML = `
        <div class="demo-modal-content">
            <div class="demo-modal-header">
                <h3>Call Our Live Demo</h3>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            <div class="demo-modal-body">
                <div class="phone-display">
                    <h2>${DEMO_PHONE_NUMBER}</h2>
                    <p>Call from any phone to experience AutoSlate in action</p>
                </div>
                <div class="demo-instructions">
                    <h4>Try These Scenarios:</h4>
                    <ul>
                        <li>🗣️ <strong>Language Test:</strong> Start speaking in Spanish, French, or any language</li>
                        <li>📅 <strong>Reservation:</strong> "I'd like to make a reservation for tonight"</li>
                        <li>🍕 <strong>Menu Questions:</strong> "What are your specials today?"</li>
                        <li>🕒 <strong>Hours:</strong> "What time do you close?"</li>
                        <li>🚫 <strong>Security Test:</strong> Try saying something inappropriate to test our filters</li>
                    </ul>
                </div>
                <div class="demo-stats">
                    <div class="stat-item">
                        <span class="stat-number" id="live-calls">0</span>
                        <span class="stat-label">Active Calls</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">23</span>
                        <span class="stat-label">Languages Today</span>
                    </div>
                    <div class="stat-item">
                        <span class="stat-number">100%</span>
                        <span class="stat-label">Uptime</span>
                    </div>
                </div>
            </div>
            <div class="demo-modal-footer">
                <button class="primary-button" onclick="copyPhoneNumber()">
                    <i data-lucide="copy"></i>
                    Copy Number
                </button>
                <button class="secondary-button" onclick="closeModal()">Close</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Re-initialize icons for the modal
    setTimeout(() => lucide.createIcons(), 100);
    
    // Close modal on background click
    modal.addEventListener('click', function(e) {
        if (e.target === modal) {
            closeModal();
        }
    });
}

// Close modal
function closeModal() {
    const modal = document.querySelector('.demo-modal');
    if (modal) {
        modal.remove();
    }
}

// Copy phone number to clipboard
function copyPhoneNumber() {
    navigator.clipboard.writeText(DEMO_PHONE_NUMBER).then(() => {
        // Show success message
        const button = document.querySelector('.demo-modal .primary-button');
        const originalText = button.innerHTML;
        button.innerHTML = '<i data-lucide="check"></i> Copied!';
        button.style.background = '#22c55e';
        
        setTimeout(() => {
            button.innerHTML = originalText;
            button.style.background = '';
            lucide.createIcons();
        }, 2000);
    });
}

// Animate demo call counter
function animateCallCounter() {
    const counter = document.getElementById('demo-calls');
    if (counter) {
        let count = 1200;
        const increment = Math.floor(Math.random() * 5) + 1;
        count += increment;
        counter.textContent = count.toLocaleString();
    }
}

// Update call counter every 30 seconds
setInterval(animateCallCounter, 30000);

// Smooth scrolling for navigation links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        }
    });
});

// Mobile menu toggle
function toggleMobileMenu() {
    const navLinks = document.querySelector('.nav-links');
    navLinks.classList.toggle('mobile-open');
}

// Add event listener for mobile menu
document.querySelector('.mobile-menu-toggle').addEventListener('click', toggleMobileMenu);

// Navbar scroll effect
window.addEventListener('scroll', function() {
    const navbar = document.querySelector('.navbar');
    if (window.scrollY > 100) {
        navbar.style.background = 'rgba(255, 255, 255, 0.98)';
        navbar.style.boxShadow = '0 2px 20px rgba(0, 0, 0, 0.1)';
    } else {
        navbar.style.background = 'rgba(255, 255, 255, 0.95)';
        navbar.style.boxShadow = 'none';
    }
});

// Intersection Observer for animations
const observerOptions = {
    threshold: 0.1,
    rootMargin: '0px 0px -50px 0px'
};

const observer = new IntersectionObserver(function(entries) {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, observerOptions);

// Observe all feature cards and pricing cards
document.addEventListener('DOMContentLoaded', function() {
    const animatedElements = document.querySelectorAll('.feature-card, .pricing-card, .comparison-row');
    
    animatedElements.forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });
});

// Add styles for demo modal
const modalStyles = `
<style>
.demo-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 2000;
    backdrop-filter: blur(5px);
}

.demo-modal-content {
    background: white;
    border-radius: 20px;
    max-width: 600px;
    width: 90%;
    max-height: 90vh;
    overflow-y: auto;
    box-shadow: 0 25px 60px rgba(0, 0, 0, 0.3);
}

.demo-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 2rem 2rem 1rem;
    border-bottom: 1px solid #e5e5e5;
}

.demo-modal-header h3 {
    font-size: 1.5rem;
    font-weight: 700;
    margin: 0;
}

.modal-close {
    background: none;
    border: none;
    font-size: 2rem;
    cursor: pointer;
    color: #666;
    padding: 0;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.modal-close:hover {
    color: #333;
}

.demo-modal-body {
    padding: 2rem;
}

.phone-display {
    text-align: center;
    margin-bottom: 2rem;
    padding: 2rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 15px;
    color: white;
}

.phone-display h2 {
    font-size: 2.5rem;
    font-weight: 800;
    margin-bottom: 0.5rem;
    color: #ffd700;
}

.demo-instructions {
    margin-bottom: 2rem;
}

.demo-instructions h4 {
    font-size: 1.25rem;
    font-weight: 700;
    margin-bottom: 1rem;
    color: #333;
}

.demo-instructions ul {
    list-style: none;
    padding: 0;
}

.demo-instructions li {
    padding: 0.75rem 0;
    border-bottom: 1px solid #f0f0f0;
}

.demo-instructions li:last-child {
    border-bottom: none;
}

.demo-stats {
    display: flex;
    gap: 1rem;
    justify-content: space-around;
    padding: 1.5rem;
    background: #f8fafc;
    border-radius: 15px;
    margin-bottom: 1rem;
}

.stat-item {
    text-align: center;
}

.stat-item .stat-number {
    display: block;
    font-size: 1.5rem;
    font-weight: 800;
    color: #667eea;
}

.stat-item .stat-label {
    font-size: 0.875rem;
    color: #666;
    font-weight: 500;
}

.demo-modal-footer {
    padding: 1rem 2rem 2rem;
    display: flex;
    gap: 1rem;
    justify-content: center;
}

.mobile-open {
    display: flex !important;
    position: absolute;
    top: 100%;
    left: 0;
    right: 0;
    background: white;
    flex-direction: column;
    padding: 1rem;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
}

@media (max-width: 768px) {
    .demo-modal-content {
        width: 95%;
        margin: 1rem;
    }
    
    .demo-modal-body {
        padding: 1.5rem;
    }
    
    .phone-display h2 {
        font-size: 2rem;
    }
    
    .demo-stats {
        flex-direction: column;
        gap: 1rem;
    }
    
    .demo-modal-footer {
        flex-direction: column;
    }
}
</style>
`;

// Inject modal styles
document.head.insertAdjacentHTML('beforeend', modalStyles);
