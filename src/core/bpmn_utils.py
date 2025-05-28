from lxml import etree

def fix_signavio_process_structure(bpmn_path):
    """
    Fixes BPMN files where the process referenced by the participant contains only lanes,
    and the actual flow elements are in a separate process.
    Overwrites the file if a fix is applied.
    """
    parser = etree.XMLParser(remove_blank_text=True)
    tree = etree.parse(bpmn_path, parser)
    root = tree.getroot()
    ns = {
        'bpmn': "http://www.omg.org/spec/BPMN/20100524/MODEL"
    }

    # Find participant and its processRef
    participant = root.find('.//bpmn:participant', ns)
    if participant is None or 'processRef' not in participant.attrib:
        return False  # Nothing to fix

    process_ref = participant.attrib['processRef']
    processes = {p.attrib['id']: p for p in root.findall('.//bpmn:process', ns)}

    if process_ref not in processes:
        return False  # Broken file

    ref_proc = processes[process_ref]

    # Check if referenced process has flow elements
    flow_tags = [
        'startEvent', 'endEvent', 'task', 'userTask', 'serviceTask', 'scriptTask',
        'manualTask', 'businessRuleTask', 'sendTask', 'receiveTask', 'callActivity',
        'subProcess', 'exclusiveGateway', 'parallelGateway', 'inclusiveGateway',
        'eventBasedGateway', 'complexGateway', 'sequenceFlow', 'boundaryEvent',
        'intermediateCatchEvent', 'intermediateThrowEvent'
    ]
    has_flow = any(ref_proc.find(f'bpmn:{tag}', ns) is not None for tag in flow_tags)

    if has_flow:
        return False  # Already correct

    # Find another process with flow elements
    for pid, proc in processes.items():
        if pid == process_ref:
            continue
        if any(proc.find(f'bpmn:{tag}', ns) is not None for tag in flow_tags):
            # Move all children except extensionElements and laneSet to ref_proc
            for elem in list(proc):
                if elem.tag.endswith('extensionElements') or elem.tag.endswith('laneSet'):
                    continue
                ref_proc.append(elem)
            # Optionally move laneSets if ref_proc has none
            if ref_proc.find('bpmn:laneSet', ns) is None:
                for lane_set in proc.findall('bpmn:laneSet', ns):
                    ref_proc.append(lane_set)
            # Remove the now-empty process
            root.remove(proc)
            # Save the fixed file
            tree.write(bpmn_path, pretty_print=True, xml_declaration=True, encoding='UTF-8')
            return True  # Fixed

    return False  # No fix applied 