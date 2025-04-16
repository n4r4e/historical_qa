// main.js
document.addEventListener('DOMContentLoaded', function() {
    // Example questions modal
    const examplesBtn = document.getElementById('examples-btn');
    const examplesModal = new bootstrap.Modal(document.getElementById('examplesModal'));
    
    // Copy button
    const copyBtn = document.getElementById('copy-btn');
    
    // Form submission event
    const queryForm = document.getElementById('query-form');
    
    // Example questions button click
    if (examplesBtn) {
        examplesBtn.addEventListener('click', function() {
            examplesModal.show();
        });
    }
    
    // Example question selection
    document.querySelectorAll('.example-question').forEach(item => {
        item.addEventListener('click', function() {
            document.getElementById('question').value = this.textContent;
            examplesModal.hide();
        });
    });
    
    // Answer copy functionality
    if (copyBtn) {
        copyBtn.addEventListener('click', function() {
            const answerText = document.getElementById('answer-text');
            
            if (answerText) {
                // Select and copy text
                const range = document.createRange();
                range.selectNodeContents(answerText);
                const selection = window.getSelection();
                selection.removeAllRanges();
                selection.addRange(range);
                document.execCommand('copy');
                selection.removeAllRanges();
                
                // Copy feedback
                const originalText = copyBtn.innerHTML;
                copyBtn.innerHTML = '<i class="fas fa-check me-1"></i>Copied';
                
                setTimeout(() => {
                    copyBtn.innerHTML = originalText;
                }, 2000);
            }
        });
    }
    
    // Asynchronous form submission via API (AJAX)
    if (queryForm) {
        queryForm.addEventListener('submit', function(e) {
            // Comment out this line if you want to use HTML form submission
            e.preventDefault();
            
            const question = document.getElementById('question').value;
            
            // Create response card if it doesn't exist
            let responseCard = document.getElementById('response-card');
            if (!responseCard) {
                responseCard = document.createElement('div');
                responseCard.id = 'response-card';
                responseCard.className = 'card';
                responseCard.innerHTML = `
                    <div class="card-header d-flex justify-content-between align-items-center">
                        <h5 class="m-0">Response</h5>
                        <button class="btn btn-sm btn-outline-secondary" id="copy-btn">
                            <i class="fas fa-copy me-1"></i>Copy
                        </button>
                    </div>
                    <div class="card-body">
                        <div class="spinner-container">
                            <div class="spinner-border text-primary" role="status">
                                <span class="visually-hidden">Loading...</span>
                            </div>
                        </div>
                    </div>
                `;
                queryForm.after(responseCard);
                
                // Add event listener to copy button
                responseCard.querySelector('#copy-btn').addEventListener('click', function() {
                    const answerText = document.getElementById('answer-text');
                    if (answerText) {
                        // Select and copy text
                        const range = document.createRange();
                        range.selectNodeContents(answerText);
                        const selection = window.getSelection();
                        selection.removeAllRanges();
                        selection.addRange(range);
                        document.execCommand('copy');
                        selection.removeAllRanges();
                        
                        // Copy feedback
                        const originalText = this.innerHTML;
                        this.innerHTML = '<i class="fas fa-check me-1"></i>Copied';
                        
                        setTimeout(() => {
                            this.innerHTML = originalText;
                        }, 2000);
                    }
                });
            } else {
                // If response card already exists, change to loading state
                responseCard.querySelector('.card-body').innerHTML = `
                    <div class="spinner-container">
                        <div class="spinner-border text-primary" role="status">
                            <span class="visually-hidden">Loading...</span>
                        </div>
                    </div>
                `;
            }
            
            // API call
            fetch('/api/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ question: question }),
            })
            .then(response => response.json())
            .then(data => {
                // Display response
                const cardBody = responseCard.querySelector('.card-body');
                if (data.detail) {
                    // Display error message
                    cardBody.innerHTML = `
                        <div class="alert alert-danger">
                            ${data.detail}
                        </div>
                    `;
                } else {
                    // Display successful response
                    cardBody.innerHTML = `
                        <div id="answer-text">
                            ${data.answer}
                        </div>
                    `;
                }
            })
            .catch(error => {
                // Error handling
                const cardBody = responseCard.querySelector('.card-body');
                cardBody.innerHTML = `
                    <div class="alert alert-danger">
                        An error occurred while processing your request: ${error.message}
                    </div>
                `;
            });
        });
    }
});