/**
 * Chat Interface for Codebase Time Machine
 */

class ChatInterface {
    constructor(repositoryId) {
        this.repositoryId = repositoryId;
        this.messages = [];
        this.isProcessing = false;
        
        this.init();
    }

    /**
     * Initialize chat interface
     */
    init() {
        this.setupEventListeners();
        this.loadChatHistory();
        this.loadSuggestions();
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');

        if (chatInput) {
            chatInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });

            chatInput.addEventListener('input', () => {
                this.updateSendButton();
            });
        }

        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                this.sendMessage();
            });
        }

        // Handle suggested query clicks
        document.addEventListener('click', (e) => {
            if (e.target.closest('#suggested-queries li')) {
                const query = e.target.textContent.replace(/['"]/g, '');
                this.sendMessage(query);
            }
        });
    }

    /**
     * Send a chat message
     */
    async sendMessage(messageText = null) {
        const chatInput = document.getElementById('chat-input');
        const message = messageText || chatInput?.value.trim();

        if (!message || this.isProcessing) return;

        // Clear input
        if (chatInput && !messageText) {
            chatInput.value = '';
        }

        this.updateSendButton();
        this.isProcessing = true;

        // Add user message to chat
        this.addMessage(message, 'user');

        // Show typing indicator
        const typingId = this.showTypingIndicator();

        try {
            // Send query to API
            const response = await api.sendChatQuery(this.repositoryId, message);

            // Remove typing indicator
            this.removeTypingIndicator(typingId);

            // Add bot response
            this.addMessage(response.response, 'bot', {
                cached: response.cached,
                timestamp: response.timestamp
            });

        } catch (error) {
            console.error('Chat error:', error);
            
            // Remove typing indicator
            this.removeTypingIndicator(typingId);

            // Show error message
            const errorMessage = APIUtils.handleError(error, 'chat');
            this.addMessage(`Sorry, I encountered an error: ${errorMessage}`, 'bot', { error: true });
        } finally {
            this.isProcessing = false;
            this.updateSendButton();
        }
    }

    /**
     * Add message to chat
     */
    addMessage(content, sender, metadata = {}) {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return;

        const messageElement = document.createElement('div');
        messageElement.className = `chat-message ${sender}-message`;

        const timestamp = new Date().toLocaleTimeString();
        
        let messageHTML = `
            <div class="message-content">
                ${this.formatMessage(content)}
            </div>
            <div class="message-meta">
                <span class="message-time">${timestamp}</span>
        `;

        if (metadata.cached) {
            messageHTML += `<span class="message-cached" title="Cached response"><i class="fas fa-clock"></i></span>`;
        }

        if (metadata.error) {
            messageElement.classList.add('error-message');
        }

        messageHTML += `</div>`;
        messageElement.innerHTML = messageHTML;

        // Remove welcome message if it exists
        const welcomeMessage = chatMessages.querySelector('.welcome-message');
        if (welcomeMessage && sender === 'user') {
            welcomeMessage.remove();
        }

        chatMessages.appendChild(messageElement);
        
        // Scroll to bottom
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Store message
        this.messages.push({
            content,
            sender,
            timestamp: new Date().toISOString(),
            ...metadata
        });

        // Limit message history
        if (this.messages.length > CONFIG.UI.CHAT_MAX_MESSAGES) {
            this.messages = this.messages.slice(-CONFIG.UI.CHAT_MAX_MESSAGES);
            
            // Remove old message elements
            const messageElements = chatMessages.querySelectorAll('.chat-message');
            if (messageElements.length > CONFIG.UI.CHAT_MAX_MESSAGES) {
                messageElements[0].remove();
            }
        }
    }

    /**
     * Format message content (support markdown)
     */
    formatMessage(content) {
        if (typeof marked !== 'undefined') {
            return marked.parse(content);
        }
        
        // Basic formatting fallback
        return content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/`(.*?)`/g, '<code>$1</code>')
            .replace(/\n/g, '<br>');
    }

    /**
     * Show typing indicator
     */
    showTypingIndicator() {
        const chatMessages = document.getElementById('chat-messages');
        if (!chatMessages) return null;

        const typingElement = document.createElement('div');
        const typingId = 'typing-' + Date.now();
        typingElement.id = typingId;
        typingElement.className = 'chat-message bot-message typing-indicator';
        typingElement.innerHTML = `
            <div class="message-content">
                <div class="typing-dots">
                    <span></span>
                    <span></span>
                    <span></span>
                </div>
            </div>
        `;

        chatMessages.appendChild(typingElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;

        return typingId;
    }

    /**
     * Remove typing indicator
     */
    removeTypingIndicator(typingId) {
        if (typingId) {
            const typingElement = document.getElementById(typingId);
            if (typingElement) {
                typingElement.remove();
            }
        }
    }

    /**
     * Update send button state
     */
    updateSendButton() {
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');

        if (chatInput && sendBtn) {
            const hasText = chatInput.value.trim().length > 0;
            sendBtn.disabled = !hasText || this.isProcessing;
            
            if (this.isProcessing) {
                sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            } else {
                sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
            }
        }
    }

    /**
     * Load chat history
     */
    async loadChatHistory() {
        try {
            const history = await api.getChatHistory(this.repositoryId, 10);
            
            if (history.history && history.history.length > 0) {
                // Clear welcome message
                const chatMessages = document.getElementById('chat-messages');
                const welcomeMessage = chatMessages?.querySelector('.welcome-message');
                if (welcomeMessage) {
                    welcomeMessage.remove();
                }

                // Add historical messages
                history.history.reverse().forEach(item => {
                    this.addMessage(item.query, 'user');
                    this.addMessage(item.response, 'bot', { 
                        cached: true,
                        timestamp: item.timestamp 
                    });
                });
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }

    /**
     * Load query suggestions
     */
    async loadSuggestions() {
        try {
            const suggestions = await api.getChatSuggestions(this.repositoryId);
            
            if (suggestions.suggestions && suggestions.suggestions.length > 0) {
                const suggestedQueries = document.getElementById('suggested-queries');
                if (suggestedQueries) {
                    suggestedQueries.innerHTML = '';
                    
                    suggestions.suggestions.slice(0, 5).forEach(suggestion => {
                        const li = document.createElement('li');
                        li.textContent = `"${suggestion}"`;
                        li.style.cursor = 'pointer';
                        suggestedQueries.appendChild(li);
                    });
                }
            }
        } catch (error) {
            console.error('Error loading suggestions:', error);
        }
    }

    /**
     * Clear chat history
     */
    clearChat() {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = `
                <div class="welcome-message">
                    <i class="fas fa-robot"></i>
                    <p>Hi! I can help you understand this repository's evolution. Try asking:</p>
                    <ul id="suggested-queries">
                        <li>"Who are the main contributors?"</li>
                        <li>"Show me the commit timeline"</li>
                        <li>"What are the development patterns?"</li>
                    </ul>
                </div>
            `;
        }
        
        this.messages = [];
        this.loadSuggestions();
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ChatInterface;
}

// Make ChatInterface available globally
window.ChatInterface = ChatInterface;