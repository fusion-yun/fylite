/* Dependency graph view. No solver or execution state is owned by this module. */
'use strict';
window.FyWorkflowGraph = (() => {
  const NS = 'http://www.w3.org/2000/svg';
  const nodeWidth = 170, nodeHeight = 72, columnGap = 42;

  /** Derive a layered DAG layout without relying on array order. */
  function layout(nodes) {
    const byId = new Map(nodes.map(node => [node.id, node]));
    const depths = new Map(), visiting = new Set();
    function depth(id) {
      if (depths.has(id)) return depths.get(id);
      if (visiting.has(id) || !byId.has(id)) throw Error('流程包含循环或缺失依赖');
      visiting.add(id);
      const deps = byId.get(id).deps;
      const value = deps.length ? Math.max(...deps.map(depth)) + 1 : 0;
      visiting.delete(id);
      depths.set(id, value);
      return value;
    }
    nodes.forEach(node => depth(node.id));
    const layers = [];
    nodes.forEach(node => (layers[depths.get(node.id)] ||= []).push(node));
    const height = Math.max(230, Math.max(...layers.map(layer => layer.length)) * 112 + 48);
    const positions = new Map();
    layers.forEach((layer, column) => {
      layer.forEach((node, row) => positions.set(node.id, {
        x: 24 + column * (nodeWidth + columnGap),
        y: height / 2 + (row - (layer.length - 1) / 2) * 112 - nodeHeight / 2
      }));
    });
    function reaches(start, target, seen = new Set()) {
      if (start === target) return true;
      if (seen.has(start)) return false;
      seen.add(start);
      return byId.get(start).deps.some(dep => reaches(dep, target, seen));
    }
    const edges = [];
    nodes.forEach(node => node.deps.forEach(dep => edges.push({
      from: dep, to: node.id, number: edges.length + 1,
      secondary: node.deps.some(other => other !== dep && reaches(other, dep))
    })));
    return { positions, edges, width: layers.length * (nodeWidth + columnGap) + 6, height };
  }

  /** Render exact dependencies; transitive edges can be hidden in the overview. */
  function render(host, options) {
    host.replaceChildren();
    if (!options.nodes.length) return;
    const graph = layout(options.nodes);
    const surface = document.createElement('div');
    surface.className = 'graph-surface';
    const extra = options.showAll ? graph.edges.filter(edge => edge.secondary).length * 16 : 0;
    surface.style.width = graph.width + 'px';
    surface.style.height = graph.height + extra + 'px';
    surface.dataset.width = graph.width;
    surface.dataset.height = graph.height + extra;
    surface.style.zoom = options.scale;
    const svg = document.createElementNS(NS, 'svg');
    svg.setAttribute('width', graph.width);
    svg.setAttribute('height', graph.height + extra);
    svg.innerHTML = '<defs><marker id="graph-arrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 Z" fill="context-stroke"/></marker></defs>';
    const related = new Set([options.selected]);
    graph.edges.forEach(edge => {
      if (edge.from === options.selected || edge.to === options.selected) {
        related.add(edge.from); related.add(edge.to);
      }
    });
    let lane = 0;
    graph.edges.forEach(edge => {
      if (edge.secondary && !options.showAll) return;
      const source = graph.positions.get(edge.from), target = graph.positions.get(edge.to);
      const x1 = source.x + nodeWidth, x2 = target.x;
      const y1 = source.y + nodeHeight / 2, y2 = target.y + nodeHeight / 2;
      const active = edge.from === options.selected || edge.to === options.selected;
      const path = document.createElementNS(NS, 'path');
      let route = `M${x1},${y1} C${x1 + 22},${y1} ${x2 - 22},${y2} ${x2},${y2}`;
      let tx = (x1 + x2) / 2, ty = (y1 + y2) / 2 - 6;
      if (edge.secondary) {
        const bottom = graph.height + lane++ * 16;
        route = `M${x1},${y1} L${x1+14},${y1} L${x1+14},${bottom} L${x2-14},${bottom} L${x2-14},${y2} L${x2},${y2}`;
        ty = bottom - 3;
      }
      path.setAttribute('d', route);
      path.setAttribute('class', 'graph-edge' + (edge.secondary ? ' secondary' : '') + (active ? ' related' : options.selected ? ' dim' : ''));
      path.setAttribute('marker-end', 'url(#graph-arrow)');
      const title = document.createElementNS(NS, 'title');
      title.textContent = `${edge.number}: ${options.title(edge.from)} → ${options.title(edge.to)}`;
      path.append(title); svg.append(path);
      const label = document.createElementNS(NS, 'text');
      label.setAttribute('x', tx); label.setAttribute('y', ty);
      label.setAttribute('class', 'edge-number'); label.textContent = edge.number;
      svg.append(label);
    });
    surface.append(svg);
    options.nodes.forEach(node => {
      const position = graph.positions.get(node.id), state = options.state(node.id);
      const button = document.createElement('button');
      button.className = 'flow-node ' + state + (options.selected === node.id ? ' active' : '') + (options.selected && !related.has(node.id) ? ' dim' : '');
      button.style.left = position.x + 'px'; button.style.top = position.y + 'px';
      button.dataset.nodeId = node.id;
      const title = document.createElement('strong'), status = document.createElement('small');
      title.textContent = options.title(node.id); status.textContent = options.status(node.id);
      button.append(title, status);
      button.title = '双击或按 Enter 打开 ' + options.title(node.id);
      // Defer rebuilding until a single-click is distinguished from a double-click.
      let timer;
      button.onclick = () => { clearTimeout(timer); timer = setTimeout(() => options.select(node.id), 220); };
      button.ondblclick = () => { clearTimeout(timer); options.open(node.id); };
      button.onkeydown = event => {
        if (event.key === 'Enter') { event.preventDefault(); options.open(node.id); }
      };
      surface.append(button);
    });
    host.append(surface);
    const omitted = graph.edges.filter(edge => edge.secondary).length;
    options.note.textContent = options.showAll ? '完整依赖：虚线为可经其他步骤追溯的输入依赖。' : `简图省略 ${omitted} 条传递依赖；勾选“完整依赖”可查看，属性区始终列出全部直接输入。`;
  }
  return { layout, render };
})();
