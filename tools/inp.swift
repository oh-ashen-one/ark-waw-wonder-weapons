// Synthetic input for the session-owned UE4Editor window. Usage:
// inp trusted | click X Y | dclick X Y | rclick X Y | move X Y | drag X1 Y1 X2 Y2 | type "text" | key NAME [cmd,shift,ctrl,alt]
import Foundation; import CoreGraphics; import ApplicationServices; import AppKit
var a = CommandLine.arguments
// DISPLAY OFFSET: tools work in "virtual" coordinates (editor at the left of the main screen); a real offset
// from .work/display_offset ("dx dy") moves everything onto another monitor without changing any script.
if let t = try? String(contentsOfFile: "/Users/YOU/ark-mashup/.work/display_offset", encoding: .utf8) {
  let o = t.split(whereSeparator: { $0 == " " || $0 == "\n" }).compactMap { Double($0) }
  if o.count == 2 && a.count > 3 {
    let pairs: [Int] = ["click","sclick","dclick","rclick","move","scroll","warp"].contains(a[1]) ? [2] :
                       ["drag","rdrag"].contains(a[1]) ? [2, 4] : []
    for i in pairs where a.count > i + 1 {
      if let x = Double(a[i]), let y = Double(a[i+1]) { a[i] = String(x + o[0]); a[i+1] = String(y + o[1]) }
    }
  }
}
// SAFETY GUARD: refuse to send any input unless the frontmost app is UE4Editor.exe (session-owned editor).
if a[1] == "activate" {
  let apps = NSWorkspace.shared.runningApplications.filter { $0.localizedName == "UE4Editor.exe" }
  guard let app = apps.first else { print("UE4Editor.exe not running"); exit(4) }
  app.activate(options: [.activateAllWindows]); usleep(500000)
  print("front:", NSWorkspace.shared.frontmostApplication?.localizedName ?? "?"); exit(0)
}
func topOwner(_ x: Double, _ y: Double) -> String {
  let list = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as! [[String: Any]]
  for w in list {  // front-to-back order
    let allowedT = (ProcessInfo.processInfo.environment["INP_TARGET"] ?? "UE4Editor.exe").split(separator: ",").map(String.init)
    guard let layer = w[kCGWindowLayer as String] as? Int, layer == 0 || allowedT.contains(w[kCGWindowOwnerName as String] as? String ?? "") else { continue }
    let b = w[kCGWindowBounds as String] as! [String: Double]
    if x >= b["X"]! && x < b["X"]! + b["Width"]! && y >= b["Y"]! && y < b["Y"]! + b["Height"]! { return w[kCGWindowOwnerName as String] as? String ?? "?" }
  }
  return "none"
}
// SAFETY GUARD (session-owned UE4Editor only):
//  - mouse actions: the topmost window under the target point must belong to UE4Editor.exe
//  - keyboard actions: UE4Editor.exe must be the frontmost application
if ["click","sclick","dclick","rclick","move","drag","rdrag","scroll"].contains(a[1]) {
  let owner = topOwner(Double(a[2])!, Double(a[3])!)
  let allowed = (ProcessInfo.processInfo.environment["INP_TARGET"] ?? "UE4Editor.exe").split(separator: ",").map(String.init)
  if !allowed.contains(owner) { FileHandle.standardError.write("ABORT: window under point is '\(owner)'; no input sent\n".data(using: .utf8)!); exit(3) }
} else if ["type","key","look","lmbdown","lmbup","warp"].contains(a[1]) {
  let name = NSWorkspace.shared.frontmostApplication?.localizedName ?? "?"
  let allowedK = (ProcessInfo.processInfo.environment["INP_TARGET"] ?? "UE4Editor.exe").split(separator: ",").map(String.init)
  if !allowedK.contains(name) { FileHandle.standardError.write("ABORT: frontmost app is '\(name)', not UE4Editor.exe; no input sent\n".data(using: .utf8)!); exit(3) }
}
// OWNER-PRESENCE GUARD: if the cursor is not where our last command left it, a human moved the mouse -> abort.
let posFile = "/Users/YOU/ark-mashup/.work/inp_lastpos"
if ProcessInfo.processInfo.environment["INP_NO_PRESENCE"] == nil, a[1] != "trusted", a[1] != "activate",
   let txt = try? String(contentsOfFile: posFile, encoding: .utf8) {
  let v = txt.split(separator: " ").compactMap { Double($0) }
  let cur = CGEvent(source: nil)!.location
  if v.count == 2 && (abs(cur.x - v[0]) > 6 || abs(cur.y - v[1]) > 6) {
    FileHandle.standardError.write("OWNER ACTIVE: cursor moved by someone else; no input sent\n".data(using: .utf8)!); exit(5)
  }
}
func savePos() { let c = CGEvent(source: nil)!.location; try? "\(c.x) \(c.y)".write(toFile: posFile, atomically: true, encoding: .utf8) }
func post(_ e: CGEvent?) { e?.post(tap: .cghidEventTap); usleep(30000) }
func mouse(_ t: CGEventType, _ x: Double, _ y: Double, _ b: CGMouseButton = .left, clicks: Int64 = 1) {
  let e = CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: CGPoint(x: x, y: y), mouseButton: b)
  e?.setIntegerValueField(.mouseEventClickState, value: clicks); post(e) }
let keys: [String: CGKeyCode] = ["return":36,"tab":48,"space":49,"delete":51,"escape":53,"left":123,"right":124,"down":125,"up":126,"f2":120,"home":115,"end":119,"forwarddelete":117,"ctrl":59,"shift":56,"cmd":55,"alt":58,"a":0,"s":1,"d":2,"f":3,"h":4,"g":5,"z":6,"x":7,"c":8,"v":9,"b":11,"q":12,"w":13,"e":14,"r":15,"y":16,"t":17,"o":31,"u":32,"i":34,"p":35,"l":37,"j":38,"k":40,"n":45,"m":46,"1":18,"2":19,"3":20,"4":21,"5":23,"6":22,"7":26,"8":28,"9":25,"0":29,"f7":98,"f5":96]
switch a[1] {
case "trusted": print(AXIsProcessTrusted())
case "move": mouse(.mouseMoved, Double(a[2])!, Double(a[3])!)
case "click": let x=Double(a[2])!, y=Double(a[3])!; mouse(.mouseMoved,x,y); mouse(.leftMouseDown,x,y); mouse(.leftMouseUp,x,y)
case "sclick":  // shift+click (multi-select ranges)
  let x=Double(a[2])!, y=Double(a[3])!
  post({ let e = CGEvent(keyboardEventSource: nil, virtualKey: 56, keyDown: true); e?.type = .flagsChanged; e?.flags = .maskShift; return e }())
  for t in [CGEventType.mouseMoved, .leftMouseDown, .leftMouseUp] { let e = CGEvent(mouseEventSource: nil, mouseType: t, mouseCursorPosition: CGPoint(x: x, y: y), mouseButton: .left); e?.flags = .maskShift; post(e) }
  post({ let e = CGEvent(keyboardEventSource: nil, virtualKey: 56, keyDown: false); e?.type = .flagsChanged; e?.flags = []; return e }())
case "dclick": let x=Double(a[2])!, y=Double(a[3])!; mouse(.mouseMoved,x,y); mouse(.leftMouseDown,x,y); mouse(.leftMouseUp,x,y); mouse(.leftMouseDown,x,y,clicks:2); mouse(.leftMouseUp,x,y,clicks:2)
case "rclick": let x=Double(a[2])!, y=Double(a[3])!; mouse(.mouseMoved,x,y); mouse(.rightMouseDown,x,y,.right); mouse(.rightMouseUp,x,y,.right)
case "drag": let x1=Double(a[2])!,y1=Double(a[3])!,x2=Double(a[4])!,y2=Double(a[5])!; mouse(.mouseMoved,x1,y1); mouse(.leftMouseDown,x1,y1); for i in 1...10 { let t=Double(i)/10; mouse(.leftMouseDragged,x1+(x2-x1)*t,y1+(y2-y1)*t) }; mouse(.leftMouseUp,x2,y2)
case "type":
  // US layout virtual keycodes (Wine reads keycodes, not unicode strings)
  let lower: [Character: CGKeyCode] = ["a":0,"s":1,"d":2,"f":3,"h":4,"g":5,"z":6,"x":7,"c":8,"v":9,"b":11,"q":12,"w":13,"e":14,"r":15,"y":16,"t":17,"1":18,"2":19,"3":20,"4":21,"6":22,"5":23,"=":24,"9":25,"7":26,"-":27,"8":28,"0":29,"]":30,"o":31,"u":32,"[":33,"i":34,"p":35,"l":37,"j":38,"'":39,"k":40,";":41,"\\":42,",":43,"/":44,"n":45,"m":46,".":47,"`":50," ":49]
  let shifted: [Character: Character] = ["_":"-","+":"=","!":"1","@":"2","#":"3","$":"4","%":"5","^":"6","&":"7","*":"8","(":"9",")":"0",":":";","\"":"'","<":",",">":".","?":"/","{":"[","}":"]","|":"\\","~":"`"]
  for ch in a[2] {
    var base = ch; var shift = false
    if ch.isUppercase { base = Character(ch.lowercased()); shift = true }
    if let b = shifted[ch] { base = b; shift = true }
    guard let k = lower[base] else { FileHandle.standardError.write("skip unmappable \(ch)\n".data(using: .utf8)!); continue }
    if shift { post(CGEvent(keyboardEventSource: nil, virtualKey: 56, keyDown: true)) }
    let d = CGEvent(keyboardEventSource: nil, virtualKey: k, keyDown: true); if shift { d?.flags = .maskShift }; post(d)
    let u = CGEvent(keyboardEventSource: nil, virtualKey: k, keyDown: false); if shift { u?.flags = .maskShift }; post(u)
    if shift { post(CGEvent(keyboardEventSource: nil, virtualKey: 56, keyDown: false)) }
  }
case "key": var fl: CGEventFlags = []; var mods: [CGKeyCode] = []
  if a.count > 3 { for m in a[3].split(separator: ",") { switch m { case "cmd": fl.insert(.maskCommand); mods.append(55); case "shift": fl.insert(.maskShift); mods.append(56); case "ctrl": fl.insert(.maskControl); mods.append(59); case "alt": fl.insert(.maskAlternate); mods.append(58); default: break } } }
  guard let k = keys[a[2]] else { FileHandle.standardError.write("unknown key \(a[2])\n".data(using: .utf8)!); exit(2) }
  var cur: CGEventFlags = []
  for (mk, mf) in zip(mods, [CGEventFlags](fl.contains(.maskCommand) ? [.maskCommand] : []) + (fl.contains(.maskShift) ? [.maskShift] : []) + (fl.contains(.maskControl) ? [.maskControl] : []) + (fl.contains(.maskAlternate) ? [.maskAlternate] : [])) { cur.insert(mf); let e = CGEvent(keyboardEventSource: nil, virtualKey: mk, keyDown: true); e?.type = .flagsChanged; e?.flags = cur; post(e) }
  let d = CGEvent(keyboardEventSource: nil, virtualKey: k, keyDown: true); d?.flags = fl; post(d); let u = CGEvent(keyboardEventSource: nil, virtualKey: k, keyDown: false); u?.flags = fl; post(u)
  for mk in mods.reversed() { let e = CGEvent(keyboardEventSource: nil, virtualKey: mk, keyDown: false); e?.type = .flagsChanged; e?.flags = []; post(e) }
case "rdrag": let x1=Double(a[2])!,y1=Double(a[3])!,x2=Double(a[4])!,y2=Double(a[5])!
  mouse(.mouseMoved,x1,y1); mouse(.rightMouseDown,x1,y1,.right)
  for i in 1...20 { let t=Double(i)/20; mouse(.rightMouseDragged,x1+(x2-x1)*t,y1+(y2-y1)*t,.right) }
  mouse(.rightMouseUp,x2,y2,.right)
case "scroll": let x=Double(a[2])!, y=Double(a[3])!; mouse(.mouseMoved,x,y); let n=Int32(a[4])!
  let e = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 1, wheel1: n, wheel2: 0, wheel3: 0); e?.location = CGPoint(x: x, y: y); post(e)
case "look":  // relative mouse look: dx dy [steps]; sets delta fields (Wine macdrv uses them when the cursor is captured)
  let dx=Int64(a[2])!, dy=Int64(a[3])!, steps = a.count > 4 ? Int(a[4])! : 1
  let p = CGEvent(source: nil)!.location
  for _ in 0..<steps { let e = CGEvent(mouseEventSource: nil, mouseType: .mouseMoved, mouseCursorPosition: p, mouseButton: .left)
    e?.setIntegerValueField(.mouseEventDeltaX, value: dx); e?.setIntegerValueField(.mouseEventDeltaY, value: dy); post(e); usleep(15000) }
case "warp": CGWarpMouseCursorPosition(CGPoint(x: Double(a[2])!, y: Double(a[3])!))
case "lmbdown": let p = CGEvent(source: nil)!.location; mouse(.leftMouseDown, p.x, p.y)
case "lmbup": let p = CGEvent(source: nil)!.location; mouse(.leftMouseUp, p.x, p.y)
default: print("?") }
savePos()
