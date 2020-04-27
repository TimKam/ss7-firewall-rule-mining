// URL for config state management
const url = new URL(window.location.href)

const nodParam = url.searchParams.get('nod')
const aggParam = url.searchParams.get('agg')
const fixParam = url.searchParams.get('fix')
const speParam = url.searchParams.get('spe')

// configuration settings
const numberOfNodes = nodParam ? Number(nodParam) : 40
const hubFixation = fixParam ? Number(fixParam) / 100 : 0.5
const aggressionLevel = aggParam ? Number(aggParam) / 100 : 0.5
const numberOfHubs = 3
const speed = speParam ? 5000 / Number(speParam) : 500
let showAttacker = false

// "file global" object to manage graph library, edges, nodes, hubs, and attackers
let cy
let edges
let nodes 
let hubs
let attacker

// utils
const genRandomInt = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min
// https://stackoverflow.com/questions/30720103/generate-random-numbers-with-logarithmic-distribution-and-custom-slope
const genLogDist = (zmii, max) => 
    Math.floor(Math.log((Math.random()*(Math.pow(zmii, max)-1.0))+1.0) / Math.log(zmii));



// edge creation functions (helpers)
const genRandomTarget = source => {
    const target = genRandomInt(0, numberOfNodes - 1)
    return target === source ? genRandomTarget(source) : target
}

const genRandomConnection = () => {
    const source = genRandomInt(0, numberOfNodes - 1)
    const target = genRandomTarget(source)
    return { source, target }
}

const genGraphBasedConnection = (source, target) => {
    if (hubs.length < numberOfHubs) {
        Object.values(edges).forEach(edge => {
            if (hubs.indexOf(edge.data.source) === -1) hubs.push(edge.data.source)
            if (hubs.indexOf(edge.data.target) === -1) hubs.push(edge.data.target)
        })
        return { source, target }
    }
    if (hubs.indexOf(Number(source)) === -1 && Math.random() < 0.15) {
        source = Number(hubs[Math.floor(Math.random() * hubs.length)])
        const hubsWithoutSource = hubs.filter(hub => hub != source)
        target = Number(hubsWithoutSource[Math.floor(Math.random() * hubsWithoutSource.length)])
        return { source, target }
    }
    if (!attacker) {
        noHubNodes = nodes.filter(node => hubs.indexOf(node.data.id) === -1)
        attacker = nodes[genRandomInt(0, nodes.length - 1)].data.id
        hubs.forEach(hubId => cy.$id(hubId).style({'background-color': '#73A790'}))
        document.getElementById('show-button').classList.remove('disabled')
    }
    if (Math.random() < (aggressionLevel / 5) && target != attacker) source = attacker
    // connect to neighboring node
    if (Math.random() < 1 - hubFixation && (source != attacker || Math.random() < 1 - aggressionLevel)) {
        const distances = nodes.map((node, index) => {
            const a = node.position.x - nodes[source].position.x
            const b = node.position.y - nodes[source].position.y
            return {
                id: index,
                distance: Math.sqrt( a*a + b*b )
            }
        })
        const sortedDistances = distances.sort((a, b) => a.distance > b.distance)
        sortedDistances.shift()
        const index = lnRandomScaled(2.75, 1.5, sortedDistances.length - numberOfNodes / 5)
        // Math.floor(Math.random() * Math.random() * Math.random() * (sortedDistances.length - numberOfNodes / 5))
        
        const result = { source, target: sortedDistances[index].id }
        return result
    } else if (source == attacker) {
        const result = { source, target }
        return result
    }
    // connect to Hub or from Hub
    const hubsPruned = hubs.filter(element => element != source && element != target)
    const hubsPrunedDistances = hubsPruned.map(
        nodeId => {
            const a = nodes[nodeId].position.x - nodes[source].position.x
            const b = nodes[nodeId].position.y - nodes[source].position.y
            return {
                id: nodeId,
                distance: Math.sqrt( a*a + b*b )
            }
        }
    ).sort((a, b) => a.distance > b.distance)
    const connectorHub = hubsPrunedDistances[0].id
    if (Math.random() < 0.5) { source = connectorHub } else { target = connectorHub }
    const result = { source, target }
    return result
}

// core logic
const startSimulation = () => {
    if(cy)  {
        cy.unmount()
        cy.destroy()
    }
    edges = {}
    hubs = []

    nodes = new Array(numberOfNodes).fill({}).map((_, index) => {
        return {
            group: 'nodes',
            data: { id: index },
            grabbable: false
        }
    })

    const render = elements => cytoscape({
        container: document.getElementById('cy'),
        elements,
        style: [
        {
            selector: 'node',
            style: {
            'background-color': '#666',
            // 'label': 'data(id)'
            }
        },
    
        {
            selector: 'edge',
            style: {
            'width': 3,
            'line-color': '#ccc',
            'target-arrow-color': '#ccc',
            'target-arrow-shape': 'triangle'
            }
        }
        ],
    })

    cy = render(nodes)
    const layout = cy.layout({name: 'random'})
    layout.run()
    nodes.forEach((node, index) => nodes[index] = {
        ...node,
        position: cy.$id(node.data.id).position()
        }
    )
    cy.zoomingEnabled(false)

    cy.ready(() => 
        setInterval(() => {
            const connection = genRandomConnection()
            const source = connection.source
            const target = connection.target
            const edgeArray = Object.values(edges)
            const existingEdge = edgeArray.find(edge => {
                return (edge.data.source == source && edge.data.target == target) ||
                    (edge.data.target == source && edge.data.source == target)
                }
            )
            const edgeId = numberOfNodes + edgeArray.length
            if (existingEdge) {
                const edgeUpdate = {
                    ...existingEdge,
                    style: { width: existingEdge.style.width + 0.2 }
                }
                edges[existingEdge.data.id] = edgeUpdate
                cy.$id(existingEdge.data.id).style('width', edgeUpdate.style.width)
            } else {
                const finalConnection = genGraphBasedConnection(source, target)
                const edge = {
                    data: {
                        id: edgeId,
                        source: finalConnection.source,
                        target: finalConnection.target
                    },
                    style: { width: 0.2 }
                }
                edges[edgeId] = edge
                cy.add([edge])
            }
            const download = { edges, nodes }
            const uriContent = `data:text/plain;charset=utf-8,${encodeURIComponent(JSON.stringify(download))}`
            document.getElementById('log-button').href = uriContent
        }, speed)
    )
}

window.addEventListener('DOMContentLoaded', _ => {
    document.getElementById('restart-button').onclick = () => location.reload()
    const showButton = document.getElementById('show-button')
    showButton.onclick = () => {
        if (showAttacker) {
            cy.$id(attacker).style({'background-color': '#F0EEE3'})
            showButton.text = "Show Attacker"
        } else {
            cy.$id(attacker).style({'background-color': '#D7B17C'})
            showButton.text = "Hide Attacker"
        }
        showAttacker = !showAttacker
    }
    window.setTimeout(() => startSimulation(), 500)
    
})

function updateConfig (id, value) {
    const label = document.getElementById(`${id.substring(0,3)}-tracker`)
    const previousLabelText = label.value
    label.value = `${previousLabelText.split(':')[0]}: ${value}`
    url.searchParams.set(id.substring(0,3), value)
    window.history.pushState({ path: url.href }, '', url.href)
}
