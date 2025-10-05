
"""
1. RUn floodlight
2. Run a topology on mininet: sudo mn --topo linear,3 --controller=remote,ip=127.0.0.1,port=6653 --switch ovsk,protocols=OpenFlow10
3. Implement the lightpath.py: python3 lightpath.py --src h1 --dst h3 --floodlight http://127.0.0.1:8080 --bidirectional
4. Show installation using floodlight REST API: curl http://127.0.0.1:8080/wm/core/switch/all/flow/json | jq

5. Show individual switches on mininet:
    sh ovs-ofctl dump-flows s1
    sh ovs-ofctl dump-flows s2
    sh ovs-ofctl dump-flows s3

ping test on mininet: h1 ping h3
"""

import requests
import json
import argparse
from collections import deque, defaultdict

HEADERS = {'Content-Type': 'application/json'}


def get_devices(floodlight_url):
    """Return list of device objects from Floodlight device API."""
    url = floodlight_url.rstrip('/') + '/wm/device/'
    r = requests.get(url)
    r.raise_for_status()
    data = r.json()
    # Normalize to list of dicts
    if isinstance(data, dict):
        return [data]
    elif isinstance(data, list):
        # If it's a list of strings (IDs), return list of dict placeholders
        if all(isinstance(x, str) for x in data):
            return [{"id": x} for x in data]
        else:
            # ensure every element is a dict (if not, wrap safely)
            normalized = []
            for x in data:
                if isinstance(x, dict):
                    normalized.append(x)
                else:
                    normalized.append({"raw": x})
            return normalized
    else:
        raise ValueError("Unexpected device API format: {}".format(type(data)))


def get_switches(floodlight_url):
    """Return list of switches (DPIDs) from Floodlight core API."""
    url = floodlight_url.rstrip('/') + '/wm/core/controller/switches/json'
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def get_topology_links(floodlight_url):
    """
    Return normalized topology links list. Will try several possible JSON field names that
    Floodlight or different versions may use.
    Each returned link will be a dict with keys: src, src_port, dst, dst_port (or skipped).
    """
    url = floodlight_url.rstrip('/') + '/wm/topology/links/json'
    r = requests.get(url)
    r.raise_for_status()
    raw = r.json()

    # Expect raw to be a list; if it's a dict with one key being the list, try to extract
    if isinstance(raw, dict) and 'links' in raw:
        raw_links = raw['links']
    else:
        raw_links = raw

    normalized = []
    if not isinstance(raw_links, list):
        # unexpected format; return empty list but print raw for debugging
        print("DEBUG: topology API returned unexpected format (not list). Raw content:")
        print(json.dumps(raw, indent=2))
        return []

    for entry in raw_links:
        if not isinstance(entry, dict):
            # skip non-dict entries but print them for debugging
            print("DEBUG: skipping non-dict topology entry:", entry)
            continue

        # try many possible key names for src/dst and port fields
        src = (entry.get('src') or entry.get('src-switch') or entry.get('srcSwitch')
               or entry.get('source') or entry.get('src_switch') or entry.get('src_switch_dpid'))
        dst = (entry.get('dst') or entry.get('dst-switch') or entry.get('dstSwitch')
               or entry.get('destination') or entry.get('dst_switch') or entry.get('dst_switch_dpid'))

        # port keys
        def get_port(e, *keys):
            for k in keys:
                v = e.get(k)
                if v is None:
                    continue
                try:
                    return int(v)
                except Exception:
                    try:
                        return int(str(v))
                    except Exception:
                        pass
            return None

        src_port = get_port(entry, 'src-port', 'src_port', 'srcPort', 'port1', 'srcPortNumber')
        dst_port = get_port(entry, 'dst-port', 'dst_port', 'dstPort', 'port2', 'dstPortNumber')

        # If the link uses slightly different naming (e.g., 'src-switch' with nested dict), handle it
        # Some Floodlight versions wrap switch names in nested fields; attempt to recover simple strings
        if isinstance(src, dict):
            src = src.get('switchDPID') or src.get('dpid') or src.get('id')
        if isinstance(dst, dict):
            dst = dst.get('switchDPID') or dst.get('dpid') or dst.get('id')

        # If either src or dst missing, print debug and skip
        if not src or not dst:
            print("DEBUG: skipping link entry due to missing src/dst. Entry:")
            print(json.dumps(entry, indent=2))
            continue

        # Normalize to Floodlight-style colon-hex DPID string if it's numeric or single int
        # (but do not attempt aggressive transformations; keep exactly what API returned)
        normalized.append({
            'src': str(src),
            'src_port': src_port,
            'dst': str(dst),
            'dst_port': dst_port
        })

    return normalized


def find_device_by_name(devices, hostname):
    """
    Attempt to locate a device object from Floodlight's devices list that matches a
    mininet host name (h1 -> .1 IPv4). Return the device dict or None.
    """
    # heuristic number from hostname (h1 -> 1)
    try:
        host_num = int(hostname.lstrip('h'))
    except Exception:
        host_num = None

    for dev in devices:
        if not isinstance(dev, dict):
            continue
        # check ipv4 as list or string
        ipv4s = dev.get('ipv4') or dev.get('ipv4Address') or dev.get('ip') or dev.get('ipv4Addresses')
        if isinstance(ipv4s, str):
            ipv4s = [ipv4s]
        if isinstance(ipv4s, list) and host_num is not None:
            for ip in ipv4s:
                try:
                    if ip.strip().endswith('.{}'.format(host_num)):
                        return dev
                except Exception:
                    pass

        # check MAC: sometimes mininet uses 00:00:00:00:00:0N or similar; not very reliable
        macs = dev.get('mac') or dev.get('macAddress') or dev.get('macs')
        if isinstance(macs, str):
            macs = [macs]
        if isinstance(macs, list) and host_num is not None:
            for m in macs:
                if m.strip().endswith('{:02x}'.format(host_num)):
                    return dev

    return None


def build_switch_graph(links):
    """
    Build adjacency mapping:
      graph[sw_dpid] = list of (neighbor_dpid, src_port_on_this_switch, dst_port_on_neighbor)
    Only well-formed links are included. DPIDs are kept as strings exactly as returned.
    """
    graph = defaultdict(list)
    for link in links:
        src = link.get('src')
        dst = link.get('dst')
        src_port = link.get('src_port')
        dst_port = link.get('dst_port')

        if not src or not dst:
            # skip invalid entries
            continue
        # If ports are None, leave them as None, but still add the neighbor relationship
        graph[src].append((dst, src_port, dst_port))
        graph[dst].append((src, dst_port, src_port))
    return graph


def shortest_switch_path(graph, src_sw, dst_sw):
    """BFS shortest path returning list of switches (dpid strings)."""
    if src_sw == dst_sw:
        return [src_sw]
    q = deque([[src_sw]])
    visited = {src_sw}
    while q:
        path = q.popleft()
        node = path[-1]
        for (nbr, _, _) in graph.get(node, []):
            if nbr in visited:
                continue
            visited.add(nbr)
            newpath = list(path) + [nbr]
            if nbr == dst_sw:
                return newpath
            q.append(newpath)
    return None


def path_ports_for_switches(graph, switch_path):
    """
    For a switch path [s1, s2, s3], compute for each hop the (in_port, out_port) on the switch.
    in_port = port on this switch to previous hop (or None)
    out_port = port on this switch to next hop (or None)
    """
    hop_ports = {}
    for i, sw in enumerate(switch_path):
        in_port = None
        out_port = None
        if i > 0:
            prev = switch_path[i - 1]
            for nbr, src_p, dst_p in graph.get(sw, []):
                if nbr == prev:
                    in_port = src_p
                    break
        if i < len(switch_path) - 1:
            nxt = switch_path[i + 1]
            for nbr, src_p, dst_p in graph.get(sw, []):
                if nbr == nxt:
                    out_port = src_p
                    break
        hop_ports[sw] = (in_port, out_port)
    return hop_ports


def push_flow(floodlight_url, switch_dpid, flow_name, in_port, out_port, priority=32768):
    """Push a single static flow to Floodlight using staticflowpusher API."""
    url = floodlight_url.rstrip('/') + '/wm/staticflowpusher/json'
    flow = {
        "switch": switch_dpid,
        "name": flow_name,
        "cookie": "0",
        "priority": str(priority),
        "active": "true"
    }
    if in_port is not None:
        flow["in_port"] = str(in_port)
    flow["actions"] = "output={}".format(out_port)
    r = requests.post(url, data=json.dumps(flow), headers=HEADERS)
    return r


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--src', required=True, help='source host (e.g. h1)')
    p.add_argument('--dst', required=True, help='destination host (e.g. h3)')
    p.add_argument('--floodlight', default='http://127.0.0.1:8080',
                   help='Floodlight base URL (default http://127.0.0.1:8080)')
    p.add_argument('--bidirectional', action='store_true', help='install flows for both directions')
    args = p.parse_args()

    fl = args.floodlight.rstrip('/')
    print("Using Floodlight URL:", fl)
    print("Discovering devices from Floodlight... (ensure hosts have been learned: run ping in Mininet if needed)")
    devices = get_devices(fl)
    print("Device count from Floodlight:", len(devices))

    src_dev = find_device_by_name(devices, args.src)
    dst_dev = find_device_by_name(devices, args.dst)

    # If automatic find failed, try to search by heuristics (attachmentPoint presence)
    def pick_attachment(dev, host_label):
        if dev is None:
            return None
        # device 'attachmentPoint' is usually a list [{'switchDPID':'00:00:00:00:00:00:00:01', 'port':1}, ...]
        ap = dev.get('attachmentPoint') or dev.get('attachmentPoints') or dev.get('attachment_point') or dev.get('attachment')
        if isinstance(ap, list) and len(ap) > 0:
            point = ap[0]
            # accept a range of field names
            sw = point.get('switchDPID') or point.get('switch') or point.get('switchId') or point.get('dpid')
            port = point.get('port') or point.get('portNumber') or point.get('port_no') or point.get('port_no')
            try:
                return (str(sw), int(port))
            except Exception:
                return None
        return None

    src_ap = pick_attachment(src_dev, args.src)
    dst_ap = pick_attachment(dst_dev, args.dst)

    # Fallback heuristics if device manager hasn't learned hosts
    if src_ap is None or dst_ap is None:
        print("Could not find device attachment by name heuristics. Attempting to infer with hostname -> linear topology mapping.")
        # Heuristic: for mininet linear,n topology: host hN usually attaches to switch with last byte N and port 1
        def heuristic(hostname):
            try:
                n = int(hostname.lstrip('h'))
            except Exception:
                return None
            # Build the usual Floodlight DPID string with decimal-padded last field
            sw_dec = "00:00:00:00:00:00:00:{:02d}".format(n)
            return (sw_dec, 1)
        if src_ap is None:
            src_ap = heuristic(args.src)
            print("Inferred src attachment:", src_ap)
        if dst_ap is None:
            dst_ap = heuristic(args.dst)
            print("Inferred dst attachment:", dst_ap)

    if src_ap is None or dst_ap is None:
        raise SystemExit("ERROR: Could not determine attachment points for src or dst. Ensure Floodlight has learned devices or modify the script for your topology.")

    src_switch, src_port = src_ap
    dst_switch, dst_port = dst_ap
    print(f"Source {args.src} -> switch {src_switch}, port {src_port}")
    print(f"Dest   {args.dst} -> switch {dst_switch}, port {dst_port}")

    # Get topology links and build graph
    links = get_topology_links(fl)
    print("Topology links retrieved:", len(links))
    if len(links) == 0:
        print("ERROR: topology API returned 0 usable link entries. Please check Floodlight topology output:")
        raw_check = requests.get(fl + '/wm/topology/links/json').text
        print(raw_check)
        raise SystemExit("Exiting due to empty topology links.")

    graph = build_switch_graph(links)
    # Debug: print graph keys
    print("Graph switch nodes:", list(graph.keys()))

    # Ensure src_switch and dst_switch are present in graph; if not, warn and still try (they might be same)
    if src_switch not in graph and src_switch != dst_switch:
        print("Warning: source switch not in topology graph; topology may be named differently.")
    if dst_switch not in graph and src_switch != dst_switch:
        print("Warning: dest switch not in topology graph; topology may be named differently.")

    sw_path = shortest_switch_path(graph, src_switch, dst_switch)
    if sw_path is None:
        if src_switch == dst_switch:
            sw_path = [src_switch]
        else:
            raise SystemExit("No path between switches found. Check topology and DPIDs. Graph nodes: {}".format(list(graph.keys())))

    print("Switch path (dpids):", " -> ".join(sw_path))

    # compute hop ports
    hop_ports = path_ports_for_switches(graph, sw_path)
    # For first switch, set in_port = src_port (host), for last switch out_port = dst_port (host)
    hop_ports[sw_path[0]] = (src_port, hop_ports[sw_path[0]][1])
    hop_ports[sw_path[-1]] = (hop_ports[sw_path[-1]][0], dst_port)

    print("Per-switch (in_port, out_port):")
    for sw in sw_path:
        print(f"  {sw}: {hop_ports[sw]}")

    # Push flows in the forward direction
    print("\nPushing forward-direction flows...")
    for i, sw in enumerate(sw_path):
        in_p, out_p = hop_ports[sw]
        if out_p is None:
            out_p = dst_port
        name = f"fwd_{args.src}_to_{args.dst}_{i+1}"
        print(f"Pushing flow to {sw}: in_port={in_p}, out={out_p}, name={name}")
        r = push_flow(fl, sw, name, in_p, out_p)
        print("  Response:", r.status_code, r.text)

    if args.bidirectional:
        print("\nPushing reverse-direction flows...")
        rev_path = list(reversed(sw_path))
        rev_hop_ports = path_ports_for_switches(graph, rev_path)
        rev_hop_ports[rev_path[0]] = (dst_port, rev_hop_ports[rev_path[0]][1])
        rev_hop_ports[rev_path[-1]] = (rev_hop_ports[rev_path[-1]][0], src_port)
        for i, sw in enumerate(rev_path):
            in_p, out_p = rev_hop_ports[sw]
            if out_p is None:
                out_p = src_port
            name = f"rev_{args.dst}_to_{args.src}_{i+1}"
            print(f"Pushing flow to {sw}: in_port={in_p}, out={out_p}, name={name}")
            r = push_flow(fl, sw, name, in_p, out_p)
            print("  Response:", r.status_code, r.text)

    print("\nDone. You can verify via Floodlight API or in Mininet: `dpctl dump-flows` for each switch or")
    print(f"GET {fl}/wm/core/switch/all/flow/json to list flows per switch on Floodlight.")


if __name__ == '__main__':
    main()

