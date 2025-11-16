// client.js (fixed)
let socket;
let username = "";
let currentMode = "global";
let targetUser = "";
let avatar = "";

let currentRoom = "global";           // active room id
const roomContainers = {};           // map room -> DOM element containing messages

let anonymousMode = false;

function toggleAnonymous() {
  anonymousMode = !anonymousMode;

  const btn = document.getElementById("anon-btn");

  if (anonymousMode) {
    btn.textContent = "Anonymous: ON";
    btn.style.background = "#e53935";  // สีแดงตอนเปิด
  } else {
    btn.textContent = "Anonymous: OFF";
    btn.style.background = "#888";     // สีเทาตอนปิด
  }
}


function openGlobal() {
  currentMode = "global";
  targetUser = "";
  // switch to the global room UI
  switchToRoom("global", "🌍 Global Chat");
  // ensure global container exists
  ensureRoomContainer("global");
  // clear any unread indicators for global (if any)
  clearUnreadBadgeForRoom("global");
  // ensure sidebar highlight
  highlightSidebarFor("global", "global");
}


// --- Sidebar selection helpers ---
function clearSidebarSelection() {
  // clear active from any item types
  document.querySelectorAll('.user-item.active, .group-item.active, .global-chat-button.active, .sidebar-item.active')
    .forEach(el => el.classList.remove('active'));
}

function highlightSidebarFor(room, modeOrTarget) {
  // modeOrTarget: 'global' | {type:'user', name} | {type:'group', name}
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

  // fallback: try element with id by room
  const el = document.getElementById(`group-${room}`) || document.getElementById(`user-${room}`);
  if (el) el.classList.add('active');
}


function ensureRoomContainer(room) {
  if (roomContainers[room]) return roomContainers[room];

  const container = document.createElement("div");
  container.className = "room-messages";
  container.id = `room-${room}`;

  // keep hidden by default — do NOT make visible here
  container.style.display = "none";
  container.style.flex = "1";
  container.style.flexDirection = "column";
  container.style.gap = "10px";
  container.style.overflowY = "auto";
  container.style.padding = "15px";

  // append into the messages parent (replace single #messages usage)
  const parent = document.getElementById("messages");
  parent.appendChild(container);

  roomContainers[room] = container;
  return container;
}

function switchToRoom(room, headerText) {
  // ensure container exists (keeps it hidden)
  ensureRoomContainer(room);

  // hide all room containers
  Object.values(roomContainers).forEach(el => el.style.display = "none");

  // show selected room
  const el = roomContainers[room];
  el.style.display = "flex"; // show flex column

  currentRoom = room;

  // update header text
  const header = document.getElementById("chat-header");
  if (headerText) header.textContent = headerText;
  else header.textContent = room === "global" ? "🌍 Global Chat" : `Room: ${room}`;

  // highlight the appropriate sidebar item
  if (room === 'global') {
    highlightSidebarFor(room, 'global');
  } else {
    // If room matches a private room pattern "Alice_Bob", we try to highlight the other user
    if (room.includes('_')) {
      const parts = room.split('_');
      const other = parts[0] === username ? parts[1] : parts[0];
      highlightSidebarFor(room, { type: 'user', name: other });
    } else {
      highlightSidebarFor(room, { type: 'group', name: room });
    }
  }

}

// append a chat message DOM to a specific room container
function addChatToRoom(room, data) {
  const container = ensureRoomContainer(room);

  // create message element
  const mine = data.sender === username;
  const div = document.createElement("div");
  div.className = `message ${mine ? "mine" : "other"}`;

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
  // auto-scroll only if this room is currently visible (user is looking at it)
  if (currentRoom === room) {
    container.scrollTop = container.scrollHeight;
  } else {
    // Optional: mark unread (simple visual cue)
    markRoomUnread(room);
  }
}

// small helper to avoid injecting raw HTML (prevent accidental broken markup)
function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function markRoomUnread(room) {
  if (room === "global") {
    const globalBtn = document.getElementById("sidebar-global");
    if (globalBtn) {
      let slot = globalBtn.querySelector('.unread-slot');
      if (!slot) {
        slot = document.createElement('span');
        slot.className = 'unread-slot';
        globalBtn.appendChild(slot);
      }
      if (!slot.querySelector('.unread-dot')) {
        const dot = document.createElement('span');
        dot.className = 'unread-dot';
        slot.appendChild(dot);
      }
    }
    return;
  }

  // group badge
  const groupEl = document.getElementById(`group-${room}`);
  if (groupEl) {
    const slot = groupEl.querySelector('.unread-slot') || groupEl.querySelector('.group-title');
    if (!slot) return;
    if (!slot.querySelector('.unread-dot')) {
      const dot = document.createElement('span');
      dot.className = 'unread-dot';
      slot.appendChild(dot);
    }
    return;
  }

  // user badge (private)
  if (room.includes('_')) {
    const parts = room.split('_');
    const other = parts[0] === username ? parts[1] : parts[0];
    const userEl = document.getElementById(`user-${other}`);
    if (userEl) {
      const slot = userEl.querySelector('.unread-slot');
      if (slot && !slot.querySelector('.unread-dot')) {
        const dot = document.createElement('span');
        dot.className = 'unread-dot';
        slot.appendChild(dot);
      }
    }
  }
}


function clearUnreadBadgeForRoom(room) {
  if (room === "global") {
    const globalBtn = document.getElementById("sidebar-global");
    if (globalBtn) {
      const dot = globalBtn.querySelector('.unread-dot');
      if (dot) dot.remove();
    }
    return;
  }

  const groupEl = document.getElementById(`group-${room}`);
  if (groupEl) {
    const dot = groupEl.querySelector('.unread-dot');
    if (dot) dot.remove();
    return;
  }

  if (room.includes('_')) {
    const parts = room.split('_');
    const other = parts[0] === username ? parts[1] : parts[0];
    const userEl = document.getElementById(`user-${other}`);
    if (userEl) {
      const dot = userEl.querySelector('.unread-dot');
      if (dot) dot.remove();
    }
  }
}


function selectAvatar(event, src) {
  avatar = "/images/" + src;
  document.querySelectorAll(".avatar-option")
    .forEach(img => img.classList.remove("avatar-selected"));
  event.target.classList.add("avatar-selected");
}

function connect() {
  username = document.getElementById("username").value.trim();
  if (!username) return alert("Please enter your name!");
  if (!avatar) return alert("Please select an avatar!");

  //socket = new WebSocket("ws://localhost:8080/ws");
  const socketURL = location.hostname === "localhost"
  ? "ws://localhost:8080/ws"
  : "wss://socket-programming-2.onrender.com/ws";
  socket = new WebSocket(socketURL);

  socket.onopen = () => {
    socket.send(JSON.stringify({
        username: username,
        avatar: avatar
    }));

    document.getElementById("user-info").innerHTML = `
      <div class="info-left">
        <img src="${avatar}" style="width:40px; height:40px; border-radius:50%;"/>
        <div style="font-weight:bold;">${escapeHtml(username)}</div>
      </div>
      <button id="disconnect-btn" class="disconnect-btn">Disconnect</button>
    `;

    document.getElementById("disconnect-btn").onclick = () => {
      socket.close();

      // reset UI
      document.getElementById("chat-screen").style.display = "none";
      document.getElementById("login-screen").style.display = "flex";

      // clear fields
      document.getElementById("username").value = "";
      document.getElementById("message").value = "";
    };



    ensureRoomContainer("global");
    switchToRoom("global", "🌍 Global Chat");

    // make sure global button is treated as a sidebar item (safety if HTML changed)
    const globalBtn = document.getElementById('sidebar-global') || document.querySelector('.global-chat-button');
    if (globalBtn) globalBtn.classList.add('sidebar-item');

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

function updateUserList(users) {
  const list = document.getElementById("user-list");
  list.innerHTML = "";
  users.forEach((u) => {
    if(u.name !== username) {
      const div = document.createElement("div");
      // ensure sidebar-item class and an id for highlight
      div.className = "user-item sidebar-item";
      div.id = `user-${u.name}`;

      div.innerHTML = `
        <div class="user-left">
          <img src="${escapeHtml(u.avatar)}" style="width: 32px; height: 32px; border-radius: 50%;">
          <span>${escapeHtml(u.name)}</span>
        </div>
        <div class="unread-slot"></div>
      `;


      // make private chat clickable
      div.onclick = () => openPrivateChat(u.name);
      list.appendChild(div);
    }
  });
}

function updateGroupList(groups) {
  const list = document.getElementById("group-list");
  list.innerHTML = "";
  groups.forEach(g => {
    if (g.kind && g.kind !== "group") return;

    if (g.name !== "global") {
      // JOIN/LEAVE button
      const btn = document.createElement("button");
      btn.style.marginLeft = "8px";
      const amMember = g.members.includes(username);
      btn.textContent = amMember ? "Leave" : "Join";
      if (!amMember) {
        btn.onclick = (e) => { e.stopPropagation(); joinGroup(g.name); };
      } else {
        btn.onclick = (e) => { e.stopPropagation(); leaveGroup(g.name, g.members.length); };
      }

      // Group Title with left container for title+badge and right-side button
      const groupTitle = document.createElement("div");
      groupTitle.className = "group-title";

      // left: title + badge slot
      const left = document.createElement("div");
      left.className = "group-left";

      const titleText = document.createElement('b');
      titleText.textContent = `${g.name} (${g.members.length})`;

      const badgeSlot = document.createElement('span');
      badgeSlot.className = 'unread-slot'; // dot will be appended here

      left.appendChild(titleText);
      left.appendChild(badgeSlot);

      // append left and button (button stays at right)
      groupTitle.appendChild(left);
      groupTitle.appendChild(btn);

      const groupMembers = document.createElement("div");
      groupMembers.className = "group-member";
      groupMembers.innerHTML = `
        <small>
          Members: ${ g.members.map(m => `<div>${escapeHtml(m)}</div>`).join("\n") }
        </small>
      `;

      const groupItem = document.createElement("div");
      groupItem.className = "group-item sidebar-item";
      groupItem.id = `group-${g.name}`;
      groupItem.append(groupTitle);
      groupItem.append(groupMembers);

      // clicking the group opens its chat window ONLY if you're a member
      groupItem.onclick = (e) => {
        if (e.target.tagName.toLowerCase() === 'button') return; // ignore clicks on buttons
        const isMember = g.members.includes(username);
        if (!isMember) {
          document.getElementById("group-name").value = g.name;
          alert("You are not a member of this group. Click Join to join first.");
          return;
        }

        // open the group's room UI
        switchToRoom(g.name, `👥 Group: ${g.name}`);
        currentMode = "group";
        document.getElementById("group-name").value = g.name;

        // clear unread badge if present
        clearUnreadBadgeForRoom(g.name);
      };

      list.appendChild(groupItem);
    }
  });
}

function createGroup() {
  const room = document.getElementById("group-name").value.trim();
  if (!room) return alert("Enter a group name to create");
  socket.send(JSON.stringify({ type: "create_group", room }));

  // open the group UI immediately (creator is member)
  switchToRoom(room, `👥 Group: ${room}`);
  highlightSidebarFor(room, { type: 'group', name: room });
  ensureRoomContainer(room);
  currentMode = "group";
}

function joinGroup(room) {
  if (!room) room = document.getElementById("group-name").value.trim();
  if (!room) return alert("Enter/select a group name");
  socket.send(JSON.stringify({ type: "join_group", room }));

  // switch to the group's room UI
  switchToRoom(room, `👥 Group: ${room}`);
  ensureRoomContainer(room);
  currentMode = "group";
  document.getElementById("group-name").value = room;

  // clear unread badge if present
  clearUnreadBadgeForRoom(room);
}

function leaveGroup(room, memberCount) {
  if (!room) return alert("No group selected");
  // send leave request to server
  socket.send(JSON.stringify({ type: "leave_group", room }));

  // clear selection input
  document.getElementById("group-name").value = "";

  // if this was the last member, ask server to delete (server handles delete when memberCount === 1)
  if (memberCount === 1) deleteGroup(room);

  // ALWAYS go back to global chat after leaving a group
  currentMode = "global";
  targetUser = "";
  switchToRoom("global", "🌍 Global Chat");
}


function deleteGroup(room) {
  if (!room) return alert("No group Selected");
  socket.send(JSON.stringify({ type: "delete_group", room }));
}


function openPrivateChat(u) {
  currentMode = "private";
  targetUser = u;

  // compute canonical room name used by server for private chats
  const room = [username, u].sort().join("_");

  // switch UI to that room and ensure container exists
  switchToRoom(room, `👤 Chat with ${u}`);
  ensureRoomContainer(room);

  // clear unread badge if present
  clearUnreadBadgeForRoom(room);

  addMessage(`Now chatting privately with ${u}`);
}

function sendMessage() {
  const text = document.getElementById("message").value.trim();
  if (!text) return;

  let payload = { 
    type: currentMode, 
    message: text,
    anonymous: anonymousMode   // ส่งสถานะ anonymous
  };

  if (currentMode === "private") {
    if (!targetUser) return alert("Choose a user to chat privately with");
    payload.target = targetUser;

    // locally open the private room so the sent message lands there
    const room = [username, targetUser].sort().join("_");
    switchToRoom(room, `👤 Chat with ${targetUser}`);
    ensureRoomContainer(room);
  }

  if (currentMode === "group") {
    const groupName = document.getElementById("group-name").value.trim();
    if (!groupName) return alert("Please select or enter a group name and join it before sending");
    payload.room = groupName;
    switchToRoom(groupName, `👥 Group: ${groupName}`);
    ensureRoomContainer(groupName);
  }

  socket.send(JSON.stringify(payload));
  document.getElementById("message").value = "";
}

function addMessage(text) {
  // put system messages into the current room's container
  const room = currentRoom || "global";
  const container = ensureRoomContainer(room);

  const div = document.createElement("div");
  div.className = "message system";
  div.textContent = text;
  container.appendChild(div);
  // only auto-scroll if user is viewing this room
  if (currentRoom === room) container.scrollTop = container.scrollHeight;
}