#!/bin/python3
"""********************************************************************************
 * Copyright (c) 2022 Ian Craggs
 *
 * This program and the accompanying materials are made available under the
 * terms of the Eclipse Public License 2.0 which is available at
 * http://www.eclipse.org/legal/epl-2.0.
 *
 * SPDX-License-Identifier: EPL-2.0
 *
 * Contributors:
 *   Ian Craggs - initial implementation
 ********************************************************************************"""

import glob, sys

reqfilename = "src/main/java/org/eclipse/sparkplug/tck/test/common/Requirements.java"

brokerids = set([])
hostids = set([])
edgeids = set([])

brokerresults = {}
hostresults = {}
edgeresults = {}

def getDescriptions():
    reqs = {}
    reqfile = open(reqfilename)
    lines = reqfile.readlines()
    id_string = None
    for curline in lines:
        curline = curline.strip()
        if curline.find("String ID_") != -1:
            id_string = curline.split()[4]
        elif id_string != None and curline.find("String "+ id_string.upper().replace("-", "_")):
            desc_string = curline.split("\"")[1].split(maxsplit=1)[1]
            #print(id_string, desc_string)
            reqs[id_string] = desc_string
            id_string = None
    reqfile.close()
    return reqs

def getTestIds(curline, iterator):
    start_found = False
    testIds = []
    while curline:
        curline = curline.strip().strip(",\t")
        if curline.find("(") != -1:
            start_found = True
            ids = curline.split("(")[1].split(",")
            testIds.extend(ids)
        elif not start_found:
            pass
        elif curline.find(");") != -1:
            curline = curline.strip(");")
            testIds.extend(curline.split(","))
            break
        else:
            testIds.extend(curline.split(","))
        curline = next(iterator, None)
    rc = set([])
    for id in testIds:
        if id.strip() != "":
            rc.add(id.strip())
    if len(rc) != len(testIds):
        for id in testIds:
            if testIds.count(id) > 1:
                print("duplicate", id)
    return rc

def process(filename):
    infile = open(filename)
    lines = infile.readlines()
    iterator = iter(lines)
    curline = next(iterator)
    while curline:
        curline = curline.strip()

        if curline.find("List<String> testIds =") != -1:
            return getTestIds(curline, iterator)

        curline = next(iterator, None)
    infile.close()
    return None

def classify_assertion(assertionid):
    edge_hints = ["EDGE", "DEVICE","NDATA", "DDATA", "DBIRTH", "NBIRTH", "DDEATH", "NDEATH", "RBE"]
    for edge_hint in edge_hints:
        if assertionid.find(edge_hint) != -1:
            return "edge"

    host_hints = ["HOST", "STATE"]
    for host_hint in host_hints:
        if assertionid.find(host_hint) != -1:
            return "host"

    #print("Assertion ", assertionid, "classified as both")
    return None

def process_test(profile, test, timestamp, lines):
    curline = lines.pop(0)
    while curline.find("OVERALL") == -1:
        assertion_id, result = curline.strip(";").split(maxsplit=1)
        if assertion_id.startswith("Monitor:"):
            assertion_id = assertion_id[len("Monitor:"):]
        assertion_id = "ID_"+assertion_id.strip(":").upper().replace("-", "_")
        result = result.strip(";\n")
        if profile == "edge":
            if assertion_id not in edgeids:
                print("Assertion not in edgeids:", assertion_id, profile, test, "probably a Monitor check")
            else:
                edgeresults[assertion_id] = test, timestamp, result
        elif profile == "host":
            if assertion_id not in hostids:
                print("Assertion not in hostids:", assertion_id, profile, test, "probably a Monitor check")
            else:
                hostresults[assertion_id] = test, timestamp, result
        elif profile == "broker":
            if assertion_id not in brokerids:
                print("Assertion not in brokerids:", assertion_id, profile, test, "probably a Monitor check")
            else:
                brokerresults[assertion_id] = test, timestamp, result
        curline = lines.pop(0)


def process_logfile(lines):
    print("Processing logfile...")
    eye = "Summary Test Results for"
    while len(lines) > 0:
        curline = lines.pop(0).strip()
        if curline.find(eye) != -1:
            date, time, rest = curline.split(maxsplit=2)
            after = curline.find(eye) + len(eye)
            profile, test = curline[after:].split(maxsplit=1)
            test = test.replace(" ", "")
            #print(profile, test)
            process_test(profile.lower(), test, date+" "+time, lines)

def stats(results):
    count = len(results)
    passes = 0
    for result in results.keys():
        if results[result] != "" and results[result][-1] == "PASS":
            passes += 1
    percent = int(passes/count * 100.0)
    return count, passes, percent

def getType(desc):
    assertion_type = ""
    if desc.find("MUST") != -1:
        assertion_type = "MUST"
    elif desc.find("SHOULD") != -1:
        assertion_type = "SHOULD"
    elif desc.find("MAY") != -1:
        assertion_type = "MAY"
    elif desc.find("must") != -1:
        assertion_type = "MUST"
        print("Error", desc)
    elif desc.find("can") != -1:
        assertion_type = "MAY"
        print("Error", desc)
    else:
        print(desc)
        sys.exit()
    return assertion_type

def isOptional(assertion_id, desc):
    optional = False
    if assertion_id.find("MULTPLE") != -1:
        optional = True
    elif assertion_id.find("REORDERING") != -1:
        optional = True
    elif assertion_id.find("TEMPLATE") != -1:
        optional = True
    elif assertion_id.find("PROPERTY") != -1:
        optional = True
    elif assertion_id.find("DATASET") != -1:
        optional = True
    elif assertion_id.find("ALIAS") != -1:
        optional = True
    elif desc.find("MUST") == -1:
        optional = True
    return optional

def export_html(profile, results, reqs):
    lines = []
    count, passed, percent = stats(results)
    lines.append("<h3>Sparkplug Profile: %s </h3>" % (profile,))
    lines.append("<h4>Assertion count: %d Number passed: %d Percent passed: %d%% </h4>" % (count, passed, percent))
    lines.append("<table border=1 width=100%>")
    lines.append( "<tr><th>%s</th><th>%s</th><th>%s</th><th>%s</th><th>%s</th></tr>" % ("Assertion ID", "Assertion Type", "Test", "Time", "Result"))
    sorted_list = list(results.keys())
    sorted_list.sort()
    for key in sorted_list:
        assertion_type = getType(descs[key])
        if isOptional(key, descs[key]):
            assertion_type += " optional"
        if results[key] == "":
            curline = "<tr><td style=\"text-align: left\">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (key, assertion_type, "", "", "")
        else:
            curline = "<tr><td style=\"text-align: left\">%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>" % (key, assertion_type, results[key][0], results[key][1], results[key][2])
        lines.append(curline)
    lines.append("</table>")
    return lines

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Test result file must be the first argument")
        sys.exit()

    descs = getDescriptions()

    logfilename = sys.argv[1]
    try:
        logfile = open(logfilename)
        loglines = logfile.readlines()
        logfile.close()
    except:
        print("Can't open logfile", logfilename)
        sys.exit()

    files = glob.glob("**/*Test.java", recursive=True)
    files.append(glob.glob("**/Monitor.java", recursive=True)[0])

    for file in files:
        if not file.endswith("TCKTest.java"):
            print("Processing", file)
            ids = process(file)
            #print(ids)
            if file.find("test/broker") != -1:
                brokerids = brokerids.union(ids)
            elif file.find("test/host") != -1:
                hostids = hostids.union(ids)
            elif file.find("test/edge") != -1:
                edgeids = edgeids.union(ids)
            elif file.find("test/Monitor") != -1:
                monitorids = ids
                for monitorid in monitorids:
                    profile = classify_assertion(monitorid)
                    if profile == "edge":
                        edgeids.add(monitorid)
                    elif profile == "host":
                        hostids.add(monitorid)
                    else: # fits into both
                        edgeids.add(monitorid)
                        hostids.add(monitorid)

    # we have all the testIds for each source file
    #print(len(brokerids), len(hostids), len(edgeids))

    for brokerid in brokerids:
        brokerresults[brokerid] = ""
    for hostid in hostids:
        hostresults[hostid] = ""
    for edgeid in edgeids:
        edgeresults[edgeid] = ""

    process_logfile(loglines)

    pre = """
    <!DOCTYPE html>
    <html>
    <head>
    <style>
    table, th, td {
        border: 1px solid black;
        border-collapse: collapse;
        text-align: center;
    }
    </style>
    </head>
    """

    post = """
    </body>
    </html>
    """

    outlines = export_html("Broker", brokerresults, descs)
    outlines.extend(export_html("Host", hostresults, descs))
    outlines.extend(export_html("Edge", edgeresults, descs))
    outlines = [pre] + outlines + [post]

    outfilename = "summary.html"
    outfile = open(outfilename, "w")
    outfile.writelines(outlines)
    outfile.close()

    print("Results summary written to", outfilename)

