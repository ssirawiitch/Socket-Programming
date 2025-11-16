let socket;
let username = "";
let currentMode = "global";
let targetUser = "";
let avatar = "";

let currentRoom = "global";           
const roomContainers = {};           

// Anonymous mode support
let isAnonymous = false;

function openGlobal() {
  currentMode = "global";
  targetUser = "";
  switchToRoom("global", "🌍 Global Chat");
  ensureRoomContainer("global");
  clearUnreadBadgeForRoom("global");
  highlightSidebarFor("global", "global");
  updateAnonymousToggleVisibility();
}

function toggleAnonymous() {
  isAnonymous = !isAnonymous;
  updateAnonymousUI();
  // Re-render all messages in current room to reflect new identity
  rerenderCurrentRoomMessages();
}

function updateAnonymousUI() {
  const checkbox = document.getElementById("anonymous-checkbox");
  const label = document.getElementById("mode-label");

  if (checkbox) checkbox.checked = isAnonymous;
  if (label) {
    label.textContent = isAnonymous ? "🕶️ Anonymous" : "👤 Normal";
    label.style.color = isAnonymous ? "#00bfa5" : "#666";
  }
}

function rerenderCurrentRoomMessages() {
  const container = roomContainers[currentRoom];
  if (!container) return;

  // Get all message elements (skip system messages)
  const messages = container.querySelectorAll('.message:not(.system)');
  
  messages.forEach(msgDiv => {
    const originalSender = msgDiv.dataset.originalSender;
    const messageIsAnonymous = msgDiv.dataset.isAnonymous === 'true';
    const sender = msgDiv.dataset.sender;
    const senderAvatar = msgDiv.dataset.senderAvatar;
    const messageText = msgDiv.dataset.messageText;
    
    if (!originalSender) return; // Skip if no data
    
    const sentByMe = originalSender === username || sender === username;
    
    let mine = false;
    let displayName = sender;
    
    if (sentByMe) {
      const currentlyAnonymous = isAnonymous;
      
      if (messageIsAnonymous === currentlyAnonymous) {
        mine = true;
        if (messageIsAnonymous) {
          displayName = sender; // "Anonymous #xxxx"
        } else {
          displayName = "You";
        }
      } else {
        mine = false;
        if (messageIsAnonymous) {
          displayName = sender; // "Anonymous #xxxx"
        } else {
          displayName = originalSender; // Real name
        }
      }
    } else {
      mine = false;
      displayName = sender;
    }
    
    // Update the message styling and content
    msgDiv.className = `message ${mine ? "mine" : "other"}`;
    msgDiv.innerHTML = `
      <div style="display:flex; gap:10px; align-items:flex-start;">
        <img src="${escapeHtml(senderAvatar)}" style="width:40px; height:40px; border-radius:50%">
        <div>
          <b>${escapeHtml(displayName)}</b><br>
          ${escapeHtml(messageText)}
        </div>
      </div>
    `;
  });
}

function updateAnonymousToggleVisibility() {
  const toggle = document.getElementById("anonymous-toggle");
  if (toggle) toggle.style.display = currentMode === "global" ? "flex" : "none";
}

function clearSidebarSelection() {
  document.querySelectorAll('.user-item.active, .group-item.active, .global-chat-button.active, .sidebar-item.active')
    .forEach(el => el.classList.remove('active'));
}

function highlightSidebarFor(room, modeOrTarget) {
  clearSidebarSelection();
  if (modeOrTarget === 'global' || room === 'global') {
    const el = document.getElementById('sidebar-global') || document.querySelector('.global-chat-button');
    if (el) el.classList.add('active');
    return;
  }
  if (modeOrTarget && modeOrTarget.type === 'user') {
    const el = document.getElementById(`user-${modeOrTarget.name}`);
    if (el) el.classList.add('active');
    return;
  }
  if (modeOrTarget && modeOrTarget.type === 'group') {
    const el = document.getElementById(`group-${modeOrTarget.name}`);
    if (el) el.classList.add('active');
    return;
  }
  const el = document.getElementById(`group-${room}`) || document.getElementById(`user-${room}`);
  if (el) el.classList.add('active');
}

function ensureRoomContainer(room) {
  if (roomContainers[room]) return roomContainers[room];

  const container = document.createElement("div");
  container.className = "room-messages";
  container.id = `room-${room}`;
  container.style.display = "none";
  container.style.flex = "1";
  container.style.flexDirection = "column";
  container.style.gap = "10px";
  container.style.overflowY = "auto";
  container.style.padding = "15px";

  const parent = document.getElementById("messages");
  parent.appendChild(container);

  roomContainers[room] = container;
  return container;
}

function switchToRoom(room, headerText) {
  ensureRoomContainer(room);
  Object.values(roomContainers).forEach(el => el.style.display = "none");
  const el = roomContainers[room];
  el.style.display = "flex"; 

  currentRoom = room;

  const header = document.getElementById("chat-header");
  const headerSpan = header.querySelector("span");
  if (headerSpan) headerSpan.textContent = headerText || (room === "global" ? "🌍 Global Chat" : `Room: ${room}`);

  if (room === 'global') highlightSidebarFor(room, 'global');
  else if (room.includes('_')) {
    const parts = room.split('_');
    const other = parts[0] === username ? parts[1] : parts[0];
    highlightSidebarFor(room, { type: 'user', name: other });
  } else highlightSidebarFor(room, { type: 'group', name: room });

  updateAnonymousToggleVisibility();
}

function addChatToRoom(room, data) {
  const container = ensureRoomContainer(room);

  console.log("=== Received message ===");
  console.log("Data:", data);
  console.log("Current username:", username);
  console.log("Current anonymous mode:", isAnonymous);
  console.log("Message is_anonymous:", data.is_anonymous);
  console.log("Message original_sender:", data.original_sender);

  // Check if this message was sent by us
  const sentByMe = data.original_sender === username || data.sender === username;
  
  console.log("Sent by me:", sentByMe);
  
  // Determine if this message should appear as "mine" (right side)
  // Logic: A message is "mine" only if:
  // - It was sent by me AND
  // - Its anonymous state matches my current anonymous state
  let mine = false;
  let displayName = data.sender;
  
  if (sentByMe) {
    const messageIsAnonymous = data.is_anonymous === true;
    const currentlyAnonymous = isAnonymous;
    
    console.log("Message anonymous:", messageIsAnonymous, "Current anonymous:", currentlyAnonymous);
    
    // Message appears as "mine" only if mode matches
    if (messageIsAnonymous === currentlyAnonymous) {
      mine = true;
      // Show "You" only for messages in current mode
      if (data.is_anonymous) {
        displayName = data.sender; // Show "Anonymous #xxxx"
      } else {
        displayName = "You";
      }
    } else {
      // Mode doesn't match - show as "other" with appropriate name
      mine = false;
      if (data.is_anonymous) {
        displayName = data.sender; // Show "Anonymous #xxxx"
      } else {
        displayName = data.original_sender || data.sender; // Show real name
      }
    }
  } else {
    // Not sent by me - always show as "other"
    mine = false;
    displayName = data.sender;
  }

  console.log("Final: mine =", mine, "displayName =", displayName);

  const div = document.createElement("div");
  div.className = `message ${mine ? "mine" : "other"}`;
  
  // Store message data for potential re-rendering when mode changes
  div.dataset.originalSender = data.original_sender || data.sender;
  div.dataset.isAnonymous = data.is_anonymous || false;
  div.dataset.sender = data.sender;
  div.dataset.senderAvatar = data.sender_avatar || '';
  div.dataset.messageText = data.message;

  const messageId = data.message_id || "";

  // top-level container id so delete events can find it
  if (messageId) div.id = `msg-${messageId}`;

  const avatarImg = `<img src="${escapeHtml(data.sender_avatar || '')}" style="width:40px; height:40px; border-radius:50%">`;

  const who = `<b>${mine ? "You" : escapeHtml(data.sender)}</b>`;
  const body = `<div>${escapeHtml(data.message)}</div>`;

  // build inner HTML
  div.innerHTML = `
    <div style="display:flex; gap:10px; align-items:flex-start;">
      ${avatarImg}
      <div style="position:relative;">
        ${who}<br>
        ${body}
      </div>
    </div>
  `;

  // if this message belongs to me, show a small delete (unsend) button
  if (mine && messageId) {
    const btn = document.createElement('button');
    btn.textContent = 'Unsend';
    btn.className = 'delete-btn';
    btn.style.marginLeft = '8px';
    btn.style.fontSize = '12px';
    btn.style.padding = '4px 8px';
    btn.style.borderRadius = '10px';
    btn.style.border = 'none';
    btn.style.background = '#ef9a9a';
    btn.style.cursor = 'pointer';
    btn.onclick = (e) => {
      e.stopPropagation();
      if (!confirm('Delete this message for everyone?')) return;
      socket.send(JSON.stringify({ type: 'delete', message_id: messageId }));
    };

    // place button inside the inner content div (the one with position:relative)
    const contentDiv = div.querySelector('div div');
    if (contentDiv) contentDiv.appendChild(btn);
    else div.querySelector('div').appendChild(btn);
  }

  container.appendChild(div);

  if (currentRoom === room) container.scrollTop = container.scrollHeight;
  else markRoomUnread(room);
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function markRoomUnread(room) {
  const el = document.getElementById(room.startsWith('user-') ? room : (room === "global" ? "sidebar-global" : `group-${room}`));
  if (!el) return;
  let slot = el.querySelector('.unread-slot');
  if (!slot) {
    slot = document.createElement('span');
    slot.className = 'unread-slot';
    el.appendChild(slot);
  }
  if (!slot.querySelector('.unread-dot')) {
    const dot = document.createElement('span');
    dot.className = 'unread-dot';
    slot.appendChild(dot);
  }
}

function clearUnreadBadgeForRoom(room) {
  const el = document.getElementById(room.startsWith('user-') ? room : (room === "global" ? "sidebar-global" : `group-${room}`));
  if (!el) return;
  const dot = el.querySelector('.unread-dot');
  if (dot) dot.remove();
}

function selectAvatar(event, src) {
  avatar = "/images/" + src;
  document.querySelectorAll(".avatar-option").forEach(img => img.classList.remove("avatar-selected"));
  event.target.classList.add("avatar-selected");
}

function connect() {
  username = document.getElementById("username").value.trim();
  if (!username) return alert("Please enter your name!");
  if (!avatar) return alert("Please select an avatar!");

  // Force localhost for testing
  const socketURL =
    (location.protocol === "https:" ? "wss://" : "ws://") +
    location.host +
    "/ws";

  socket = new WebSocket(socketURL);

  socket.onopen = () => {
    socket.send(JSON.stringify({ username, avatar }));

    document.getElementById("user-info").innerHTML = `
      <div class="info-left">
        <img src="${avatar}" style="width:40px; height:40px; border-radius:50%;"/>
        <div style="font-weight:bold;">${escapeHtml(username)}</div>
      </div>
      <button id="disconnect-btn" class="disconnect-btn">Disconnect</button>
    `;

    document.getElementById("disconnect-btn").onclick = () => {
      socket.close();
      document.getElementById("chat-screen").style.display = "none";
      document.getElementById("login-screen").style.display = "flex";
      document.getElementById("username").value = "";
      document.getElementById("message").value = "";
    };

    ensureRoomContainer("global");
    switchToRoom("global", "🌍 Global Chat");
    updateAnonymousToggleVisibility();
  };

  socket.onmessage = (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "error") {
      // Only treat username-conflict as a fatal error that closes the socket.
      // Other error messages are advisory (e.g., "You are not a member of group 'x'")
      alert(data.message);
      if (typeof data.message === 'string' && data.message.includes('Username already exists')) {
        socket.close();
      }
      return;
    }

    if (data.type === "user_list") {
      updateUserList(data.users);
      return;
    }

    if (data.type === "group_list") {
      updateGroupList(data.groups);
      return;
    }


    if (data.type === "system") {
      addMessage(data.message);
      return;
    }

    if (data.type === "chat") {
      // server includes `room` for every chat broadcast (global / private / group)
      const room = data.room || "global";
      addChatToRoom(room, data);
      return;
    }

    if (data.type === "delete") {
      const mid = data.message_id;
      if (!mid) return;
      const el = document.getElementById(`msg-${mid}`);
      if (el) {
        el.innerHTML = `<i style="color:gray">Message deleted</i>`;
        el.classList.add('deleted');
      }
      return;
    }
  };

  socket.onclose = () => addMessage("Disconnected");

  document.getElementById("login-screen").style.display = "none";
  document.getElementById("chat-screen").style.display = "flex";
}

function sendMessage() {
  const text = document.getElementById("message").value.trim();
  if (!text) return;
  let payload = { type: currentMode, message: text };

  if (currentMode === "global" && isAnonymous) payload.anonymous = true;
  
  console.log("Sending message:", payload);
  console.log("Current anonymous mode:", isAnonymous);
  
  if (currentMode === "private") {
    if (!targetUser) return alert("Choose a user");
    payload.target = targetUser;
    const room = [username, targetUser].sort().join("_");
    switchToRoom(room, `👤 Chat with ${targetUser}`);
    ensureRoomContainer(room);
  }
  if (currentMode === "group") {
    const room = document.getElementById("group-name").value.trim();
    if (!room) return alert("Please join a group first");
    payload.room = room;
    switchToRoom(room, `👥 Group: ${room}`);
    ensureRoomContainer(room);
  }
  socket.send(JSON.stringify(payload));
  document.getElementById("message").value = "";
}

function addMessage(text) {
  const room = currentRoom || "global";
  const container = ensureRoomContainer(room);
  const div = document.createElement("div");
  div.className = "message system";
  div.textContent = text;
  container.appendChild(div);
  if (currentRoom === room) container.scrollTop = container.scrollHeight;
}
