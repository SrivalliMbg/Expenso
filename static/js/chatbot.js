/** Floating AI Financial Assistant - works on any page with #floating-chatbot-container */
(function() {
    function getChatHistory() {
        return JSON.parse(sessionStorage.getItem('chatHistory') || '[]');
    }
    function addToChatHistory(sender, text) {
        var history = getChatHistory();
        history.push({ sender: sender, text: text, timestamp: new Date().toISOString() });
        if (history.length > 20) history = history.slice(-20);
        sessionStorage.setItem('chatHistory', JSON.stringify(history));
    }
    function addMessage(text, sender) {
        var el = document.getElementById('chat-messages');
        if (!el) return;
        var div = document.createElement('div');
        div.className = 'message ' + sender + '-message';
        var content = document.createElement('div');
        content.className = 'message-content';
        content.innerHTML = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>').replace(/•/g, '&bull;');
        div.appendChild(content);
        el.appendChild(div);
        el.scrollTop = el.scrollHeight;
        addToChatHistory(sender, text);
    }
    function addTyping() {
        var el = document.getElementById('chat-messages');
        if (!el) return;
        var div = document.createElement('div');
        div.className = 'message bot-message typing-indicator';
        div.id = 'typing-indicator';
        div.innerHTML = '<div class="message-content">Thinking...</div>';
        el.appendChild(div);
        el.scrollTop = el.scrollHeight;
    }
    function removeTyping() {
        var el = document.getElementById('typing-indicator');
        if (el) el.remove();
    }
    window.sendMessage = function() {
        var input = document.getElementById('chat-input');
        var msg = input && input.value.trim();
        if (!msg) return;
        addMessage(msg, 'user');
        input.value = '';
        addTyping();
        var user = null;
        try { user = JSON.parse(sessionStorage.getItem('user')); } catch (e) {}
        var body = {
            user_id: (user && user.id) || null,
            message: msg,
            user_mode: (user && user.status) || 'professional',
            profile_data: { Name: (user && user.username) || '', Status: (user && user.status) || 'professional', Profession: (user && user.profession) || '' },
            chat_history: getChatHistory()
        };
        fetch('/api/chatbot', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
            .then(function(r) { return r.json(); })
            .then(function(d) { removeTyping(); addMessage(d.response || 'No response.', 'bot'); })
            .catch(function() { removeTyping(); addMessage('Sorry, I had trouble connecting. Try again?', 'bot'); });
    };
    window.expandChatbot = function() {
        var b = document.getElementById('chatbot-body'), w = document.getElementById('chatbot-widget');
        if (b && b.style.display === 'none') { b.style.display = 'block'; if (w) w.classList.remove('minimized'); var i = document.getElementById('chat-input'); if (i) i.focus(); }
    };
    window.toggleChatbot = function(e) { if (e) e.stopPropagation(); var b = document.getElementById('chatbot-body'), t = document.getElementById('chatbot-toggle-btn'), w = document.getElementById('chatbot-widget'); if (!b) return; if (b.style.display === 'none') { b.style.display = 'block'; if (t) t.textContent = '\u2715'; if (w) w.classList.remove('minimized'); var i = document.getElementById('chat-input'); if (i) i.focus(); } else { b.style.display = 'none'; if (t) t.textContent = '\uD83D\uDCAC'; if (w) w.classList.add('minimized'); } };
    window.handleChatKeyPress = function(e) { if (e.key === 'Enter') window.sendMessage(); };
    window.askQuickQuestion = function(q) { var i = document.getElementById('chat-input'); if (i) { i.value = q; window.sendMessage(); } };
    window.showChatbotNotification = function() { var n = document.getElementById('chatbot-notification'); if (n) n.style.display = 'flex'; };
    window.hideChatbotNotification = function() { var n = document.getElementById('chatbot-notification'); if (n) n.style.display = 'none'; };
    function init() {
        var c = document.getElementById('floating-chatbot-container');
        if (!c || c.children.length > 0) return;
        c.innerHTML = '<div class="chatbot-widget" id="chatbot-widget"><div class="chatbot-header" onclick="expandChatbot()"><h4>\uD83E\uDD16 AI Financial Assistant</h4><div style="position:relative"><button class="chatbot-toggle" onclick="toggleChatbot(event)" id="chatbot-toggle-btn">\uD83D\uDCAC</button><div class="chatbot-notification" id="chatbot-notification" style="display:none">!</div></div></div><div class="chatbot-body" id="chatbot-body" style="display:none"><div class="chat-messages" id="chat-messages"><div class="message bot-message"><div class="message-content">Hey! I can help with budget, savings, investments, stocks, loans, cards. What do you want to look at?</div></div></div><div class="chat-input-container"><input type="text" id="chat-input" placeholder="Chat with Expenso..." onkeypress="handleChatKeyPress(event)"><button onclick="sendMessage()" class="send-btn">Send</button></div><div class="quick-actions"><button onclick="askQuickQuestion(\'Analyze my budget\')" class="quick-btn">\uD83D\uDCB0 Budget</button><button onclick="askQuickQuestion(\'How can I save more?\')" class="quick-btn">\uD83D\uDCA1 Savings</button><button onclick="askQuickQuestion(\'Show me stocks under 500\')" class="quick-btn">\uD83D\uDCC8 Stocks</button></div></div></div>';
        var w = document.getElementById('chatbot-widget'), b = document.getElementById('chatbot-body');
        if (w) w.classList.add('minimized');
        if (b) b.style.display = 'none';
        setTimeout(function() { if (window.showChatbotNotification) window.showChatbotNotification(); }, 3000);
    }
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
})();
