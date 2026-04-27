document.addEventListener("DOMContentLoaded", () => {
 const TEAMS_JSON = JSON.parse(document.getElementById("org-teams-data").textContent);
 const DEPS_JSON = JSON.parse(document.getElementById("org-deps-data").textContent);
 const firstDept = document.querySelector(".org-dept");
  if (firstDept) {
    firstDept.classList.add("org-dept--expanded");
    const firstBody = firstDept.querySelector(".org-dept__body");
    if (firstBody) firstBody.style.display = "block";
  }
  const tabs = document.querySelectorAll("[data-tab]");
  const panels = {
    departments: document.getElementById("tab-departments"),
    dependencies: document.getElementById("tab-dependencies"),
    types: document.getElementById("tab-types"),
  };

  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      tabs.forEach((btn) => btn.classList.remove("sky-toggle__btn--active"));
      tab.classList.add("sky-toggle__btn--active");

      Object.values(panels).forEach((panel) => {
        if (panel) panel.style.display = "none";
      });

      const selected = tab.dataset.tab;
      if (panels[selected]) panels[selected].style.display = "block";
      const toolbarSearch = document.querySelector(".org-toolbar .sky-field");
      const toolbarFilter = document.getElementById("org-dept-filter");

        if (selected === "dependencies") {
        if (toolbarSearch) toolbarSearch.style.display = "none";
        if (toolbarFilter) toolbarFilter.style.display = "none";
        } else {
        if (toolbarSearch) toolbarSearch.style.display = "";
        if (toolbarFilter) toolbarFilter.style.display = "";
        }
      if (selected === "dependencies") drawDependencyGraph();
    });
  });

  document.querySelectorAll("[data-dept-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const dept = button.closest(".org-dept");
      const body = dept.querySelector(".org-dept__body");

      dept.classList.toggle("org-dept--expanded");
      body.style.display = body.style.display === "none" ? "block" : "none";
    });
  });

  const searchInput = document.getElementById("org-search-input");
  const deptFilter = document.getElementById("org-dept-filter");

  function applyFilters() {
  const query = (searchInput?.value || "").toLowerCase();
  const deptId = deptFilter?.value || "";

  document.querySelectorAll(".org-dept").forEach((dept) => {
    const matchesDept = !deptId || dept.dataset.deptId === deptId;
    const matchesSearch = dept.innerText.toLowerCase().includes(query);
    dept.style.display = matchesDept && matchesSearch ? "block" : "none";
  });

  document.querySelectorAll(".org-type-card").forEach((card) => {
    const matchesDept = !deptId || card.dataset.deptId === deptId;
    const matchesSearch = card.innerText.toLowerCase().includes(query);
    card.style.display = matchesDept && matchesSearch ? "block" : "none";
  });
}

  searchInput?.addEventListener("input", applyFilters);
  deptFilter?.addEventListener("change", applyFilters);

  const overlay = document.getElementById("org-detail-overlay");
  const detailTitle = document.getElementById("detail-title");
  const detailSubtitle = document.getElementById("detail-subtitle");
  const detailTypeBadge = document.getElementById("detail-type-badge");
  const detailBody = document.getElementById("detail-body");
  const closeBtn = document.getElementById("detail-close");
  const backdrop = document.getElementById("org-detail-backdrop");

  function findTeam(teamId) {
    return TEAMS_JSON.find((team) => Number(team.team_id) === Number(teamId));
  }

  function openTeamDetail(teamId) {
    const team = findTeam(teamId);
    if (!team) return;

    detailTitle.textContent = team.name;
    detailSubtitle.textContent = `${team.department_name} • ${team.member_count} engineers`;
    detailTypeBadge.innerHTML = `<span class="org-type-badge">${team.type_name}</span>`;

    detailBody.innerHTML = `
      <div class="org-detail__actions">
  
    <span class="sky-badge sky-badge--positive org-detail-status">
    ● ${team.status_display}
    </span>

    <button id="org-action-message" class="sky-btn sky-btn--primary" type="button">
    <span class="sky-icon" data-icon="Mail" data-size="14"></span>
    Email Team
    </button>

    <button id="org-action-schedule" class="sky-btn sky-btn--primary" type="button">
    <span class="sky-icon" data-icon="Calendar" data-size="14"></span>
    Schedule Meeting
    </button>

    </div>

      <div class="org-detail__section">
        <h3 class="org-detail__section-title">Mission & Responsibilities</h3>
        <div class="org-info-pill">
          <div class="org-info-pill__label">Purpose</div>
          <div class="org-info-pill__value">${team.description}</div>
        </div>
        <br>
        <div class="org-info-pill">
          <div class="org-info-pill__label">Responsibilities</div>
          <div class="org-info-pill__value">${team.responsibilities}</div>
        </div>
      </div>

      <div class="org-detail__section">
        <h3 class="org-detail__section-title">Team Information</h3>
        <div class="org-detail__grid">
          <div class="org-info-pill"><div class="org-info-pill__label">Manager</div><div class="org-info-pill__value">${team.manager_name}</div></div>
          <div class="org-info-pill"><div class="org-info-pill__label">Status</div><div class="org-info-pill__value">${team.status_display}</div></div>
          <div class="org-info-pill"><div class="org-info-pill__label">Agile Practice</div><div class="org-info-pill__value">${team.agile_practice}</div></div>
          <div class="org-info-pill"><div class="org-info-pill__label">Contact Channel</div><div class="org-info-pill__value">${team.contact_channel}</div></div>
        </div>
      </div>

      <div class="org-detail__section">
        <h3 class="org-detail__section-title">Team Members</h3>
        ${team.members.map(member => `
          <div class="org-member-row">
            <div class="org-member-avatar">${member.initials}</div>
            <div>
              <span class="org-member-name">${member.name}</span>
              <span class="org-member-pos">${member.position}</span>
              <div class="org-member-user">${member.email}</div>
            </div>
          </div>
        `).join("")}
      </div>

      <div class="org-detail__section">
        <h3 class="org-detail__section-title">Code Repositories</h3>
        ${team.repositories.length ? team.repositories.map(repo => `
          <div class="org-repo-row">
            <span class="org-repo-url">${repo.url || repo.name}</span>
            ${repo.is_main ? `<span class="org-repo-main">Main</span>` : ""}
          </div>
        `).join("") : "<p>No repositories recorded.</p>"}
      </div>

      <div class="org-detail__section">
        <h3 class="org-detail__section-title">Dependencies</h3>
        ${team.depends_on.length ? team.depends_on.map(dep => `
          <div class="org-dep-row org-dep-row--down">
            <span class="org-dep-arrow--down">→</span>
            <span class="org-dep-name">Depends on ${dep.to_name}</span>
          </div>
        `).join("") : "<p>No upstream dependencies recorded.</p>"}

        ${team.depended_on_by.length ? team.depended_on_by.map(dep => `
          <div class="org-dep-row org-dep-row--up">
            <span class="org-dep-arrow--up">←</span>
            <span class="org-dep-name">${dep.from_name} depends on this team</span>
          </div>
        `).join("") : ""}
      </div>
    `;

    overlay.classList.add("sky-slide-panel--open");
    detailBody.querySelectorAll(".sky-icon[data-icon]").forEach((el) => {
    const name = el.dataset.icon;
    const size = parseInt(el.dataset.size, 10) || 18;
    if (window.SKY_ICONS && SKY_ICONS[name]) {
        el.innerHTML = SKY_ICONS[name](size);
    }
    });
    const messageBtn = document.getElementById("org-action-message");
    if (messageBtn) {
    messageBtn.addEventListener("click", () => {
        window.location.href = "/messages/";
    });
    }
    const scheduleBtn = document.getElementById("org-action-schedule");
    if (scheduleBtn) {
    scheduleBtn.addEventListener("click", () => {
        window.location.href = "/schedule/";
    });
}
  }
    function closeTeamDetail() {
    overlay.classList.remove("sky-slide-panel--open");
    }

    document.addEventListener("click", (event) => {
    if (
        event.target.closest("#detail-close") ||
        event.target.closest("#org-detail-backdrop")
    ) {
        event.preventDefault();
        closeTeamDetail();
    }
    });

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeTeamDetail();
        }
        });
        document.addEventListener("click", (event) => {
    const teamCard = event.target.closest("[data-team-id]");

    if (!teamCard) return;

    const teamId = teamCard.dataset.teamId;
    if (!teamId) return;

    openTeamDetail(teamId);
    });

  function drawDependencyGraph() {
  const svg = document.getElementById("depGraph");
  if (!svg || !TEAMS_JSON.length) return;

  svg.innerHTML = "";

  const width = svg.clientWidth || 1120;
  const height = svg.clientHeight || 600;

  const typeColours = {
    Platform: "#0010f5",
    Product: "#6626a1",
    Infrastructure: "#f15a22",
    Data: "#0b3a6d",
    Security: "#007e13",
    Engineering: "#0010f5",
    Unassigned: "#8d8d8d",
  };

  const departmentLayout = [
    { name: "Platform", x: width * 0.23, y: height * 0.56, r: 210, colour: "#0010f5" },
    { name: "Product", x: width * 0.50, y: height * 0.52, r: 210, colour: "#6626a1" },
    { name: "Data", x: width * 0.76, y: height * 0.56, r: 205, colour: "#0b3a6d" },
    { name: "Customer Experience", x: width * 0.48, y: height * 0.90, r: 190, colour: "#f15a22" },
  ];

  const departments = [...new Set(TEAMS_JSON.map((team) => team.department_name))];

  function getDeptLayout(deptName, index) {
    const byName = departmentLayout.find((item) =>
      deptName.toLowerCase().includes(item.name.toLowerCase()) ||
      item.name.toLowerCase().includes(deptName.toLowerCase())
    );

    if (byName) return byName;

    return {
      name: deptName,
      x: width * (0.24 + (index % 3) * 0.26),
      y: height * (0.50 + Math.floor(index / 3) * 0.28),
      r: 190,
      colour: ["#0010f5", "#6626a1", "#0b3a6d", "#f15a22"][index % 4],
    };
  }

  const layouts = {};
  departments.forEach((deptName, index) => {
    layouts[deptName] = getDeptLayout(deptName, index);
  });

  const teamsByDept = {};
  TEAMS_JSON.forEach((team) => {
    if (!teamsByDept[team.department_name]) teamsByDept[team.department_name] = [];
    teamsByDept[team.department_name].push(team);
  });

  const positions = {};
  Object.entries(teamsByDept).forEach(([deptName, teams]) => {
    const layout = layouts[deptName];
    const angleStart = -Math.PI / 2;

    teams.forEach((team, index) => {
      const angle = angleStart + (index / Math.max(teams.length, 1)) * Math.PI * 2;
      const nodeRadius = teams.length === 1 ? 0 : layout.r * 0.42;

      positions[team.team_id] = {
        x: layout.x + nodeRadius * Math.cos(angle),
        y: layout.y + nodeRadius * Math.sin(angle),
      };
    });
  });

  function makeSvgElement(tag, attrs = {}) {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, value));
    return element;
  }

  const defs = makeSvgElement("defs");
  defs.innerHTML = `
    <marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3"
      orient="auto" markerUnits="strokeWidth">
      <path d="M0,0 L0,6 L8,3 z" fill="#9b9b9b"></path>
    </marker>
    <filter id="nodeShadow" x="-35%" y="-35%" width="170%" height="170%">
      <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#0010f5" flood-opacity="0.10"/>
    </filter>
  `;
  svg.appendChild(defs);

    const viewport = makeSvgElement("g", { id: "graphViewport" });
    const clusterLayer = makeSvgElement("g");
    const edgeLayer = makeSvgElement("g");
    const nodeLayer = makeSvgElement("g");

    viewport.appendChild(clusterLayer);
    viewport.appendChild(edgeLayer);
    viewport.appendChild(nodeLayer);
    svg.appendChild(viewport);

    let zoom = 1;
    const zoomLabel = document.getElementById("graph-zoom-label");
    const zoomInBtn = document.getElementById("graph-zoom-in");
    const zoomOutBtn = document.getElementById("graph-zoom-out");
    const resetBtn = document.getElementById("graph-reset");

  function applyZoom() {
    viewport.setAttribute(
      "transform",
      `translate(${width / 2} ${height / 2}) scale(${zoom}) translate(${-width / 2} ${-height / 2})`
    );

    if (zoomLabel) zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
  }

  zoomInBtn?.replaceWith(zoomInBtn.cloneNode(true));
  zoomOutBtn?.replaceWith(zoomOutBtn.cloneNode(true));
  resetBtn?.replaceWith(resetBtn.cloneNode(true));

  document.getElementById("graph-zoom-in")?.addEventListener("click", () => {
    zoom = Math.min(1.6, zoom + 0.1);
    applyZoom();
  });

  document.getElementById("graph-zoom-out")?.addEventListener("click", () => {
    zoom = Math.max(0.7, zoom - 0.1);
    applyZoom();
  });

  document.getElementById("graph-reset")?.addEventListener("click", () => {
    zoom = 1;
    applyZoom();
  });

  applyZoom();

  Object.values(layouts).forEach((layout) => {
    const circle = makeSvgElement("circle", {
      cx: layout.x,
      cy: layout.y,
      r: layout.r,
      fill: layout.colour,
      "fill-opacity": "0.018",
      stroke: layout.colour,
      "stroke-opacity": "0.22",
      "stroke-width": "1.4",
      "stroke-dasharray": "8 8",
    });

    const label = makeSvgElement("text", {
      x: layout.x,
      y: layout.y - layout.r + 18,
      "text-anchor": "middle",
      "font-size": "14",
      "font-weight": "800",
      fill: layout.colour,
      opacity: "0.42",
    });
    label.textContent = layout.name;

    clusterLayer.appendChild(circle);
    clusterLayer.appendChild(label);
  });

  DEPS_JSON.forEach((dep) => {
    const from = positions[dep.from];
    const to = positions[dep.to];
    if (!from || !to) return;

    const line = makeSvgElement("line", {
      x1: from.x,
      y1: from.y,
      x2: to.x,
      y2: to.y,
      stroke: "#8f8f8f",
      "stroke-width": "1.8",
       opacity: "0.42",
      "marker-end": "url(#arrow)",
    });

    edgeLayer.appendChild(line);
  });

  TEAMS_JSON.forEach((team) => {
    const pos = positions[team.team_id];
    if (!pos) return;

    const teamColour = typeColours[team.type_name] || team.type_colour || "#0010f5";
    const initials = team.name
      .split(" ")
      .map((word) => word[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();

    const group = makeSvgElement("g");
    group.style.cursor = "pointer";
    group.dataset.teamId = team.team_id;

    group.addEventListener("click", () => openTeamDetail(team.team_id));

    const node = makeSvgElement("circle", {
      cx: pos.x,
      cy: pos.y,
      r: "38",
      fill: "#ffffff",
      stroke: teamColour,
      "stroke-width": "1.8",
      opacity: "0.98",
      filter: "url(#nodeShadow)",
    });

    const dot = makeSvgElement("circle", {
      cx: pos.x,
      cy: pos.y - 26,
      r: "4",
      fill: teamColour,
    });

    const text = makeSvgElement("text", {
      x: pos.x,
      y: pos.y + 6,
      "text-anchor": "middle",
      "font-size": "13",
      "font-weight": "800",
      fill: teamColour,
    });
    text.textContent = initials;

    const label = makeSvgElement("text", {
      x: pos.x,
      y: pos.y + 58,
      "text-anchor": "middle",
      "font-size": "12",
      "font-weight": "700",
      fill: "#4a4a4a",
    });
    label.textContent = team.name.length > 16 ? `${team.name.slice(0, 15)}...` : team.name;

    group.appendChild(node);
    group.appendChild(dot);
    group.appendChild(text);
    group.appendChild(label);
    nodeLayer.appendChild(group);
  });

  nodeLayer.querySelectorAll("g").forEach((nodeGroup) => {
    nodeGroup.addEventListener("mouseenter", () => {
      const teamId = Number(nodeGroup.dataset.teamId);

      edgeLayer.querySelectorAll("line").forEach((line) => {
        line.setAttribute("opacity", "0.12");
        line.setAttribute("stroke", "#c7c7c7");
        line.setAttribute("stroke-width", "1.4");
      });

      DEPS_JSON.forEach((dep, index) => {
        if (dep.from === teamId || dep.to === teamId) {
          const activeLine = edgeLayer.children[index];
          if (activeLine) {
            activeLine.setAttribute("opacity", "0.95");
            activeLine.setAttribute("stroke", "#0010f5");
            activeLine.setAttribute("stroke-width", "2.4");
          }
        }
      });

      nodeLayer.querySelectorAll("g").forEach((otherNode) => {
        otherNode.setAttribute("opacity", "0.22");
      });
      nodeGroup.setAttribute("opacity", "1");
    });

    nodeGroup.addEventListener("mouseleave", () => {
      edgeLayer.querySelectorAll("line").forEach((line) => {
        line.setAttribute("opacity", "0.32");
        line.setAttribute("stroke", "#9b9b9b");
        line.setAttribute("stroke-width", "1.6");
      });

      nodeLayer.querySelectorAll("g").forEach((otherNode) => {
        otherNode.setAttribute("opacity", "1");
      });
    });
  });
}
});