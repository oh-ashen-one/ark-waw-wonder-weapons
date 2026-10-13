// Prints "<windowID> <x> <y> <w> <h> <title>" for on-screen windows owned by argv[1].
import CoreGraphics
import Foundation
var dx = 0.0, dy = 0.0
if let t = try? String(contentsOfFile: "/Users/YOU/ark-mashup/.work/display_offset", encoding: .utf8) {
  let o = t.split(whereSeparator: { $0 == " " || $0 == "\n" }).compactMap { Double($0) }
  if o.count == 2 { dx = o[0]; dy = o[1] }
}
let list = CGWindowListCopyWindowInfo(.optionOnScreenOnly, kCGNullWindowID) as! [[String: Any]]
for w in list where (w[kCGWindowOwnerName as String] as? String ?? "") == CommandLine.arguments[1] {
  let b = w[kCGWindowBounds as String] as! [String: Any]
  print(w[kCGWindowNumber as String]!, Int((b["X"] as! Double) - dx), Int((b["Y"] as! Double) - dy), b["Width"]!, b["Height"]!, w[kCGWindowName as String] ?? "")
}
