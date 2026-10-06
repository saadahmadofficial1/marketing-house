// sa_ocr — read text out of images using macOS's own Vision framework.
//
// Built 1 Sep 2026 for a role-label audit of a training series: 26 sign-in moments needed
// the top-right corner read, and neither obvious option was right. Routine checks run
// locally rather than through a hosted vision model, and a 26-frame Ollama batch makes
// the Mac stutter while Saad is working (heavy Ollama runs 1–6 am only). Apple’s Vision
// runs on-device, in milliseconds, with nothing installed: this check runs locally and
// uploads nothing.
//
//   swiftc -O Tools/sa_ocr.swift -o Tools/bin/sa_ocr
//   Tools/bin/sa_ocr shot.png [more.png ...]
//
// Prints one line per image:  <path>\t<text with newlines as " | ">
import Foundation
import Vision
import AppKit

// --boxes (added 23 Sep 2026, for a mobile-app series): also print WHERE each line is, so a
// call-out box can be placed on the exact element instead of measured by hand. Vision
// already computes the rectangle; we were simply throwing it away. Without the flag the
// output is byte-for-byte what it always was, so nothing downstream changes.
var args = Array(CommandLine.arguments.dropFirst())
let wantBoxes = args.contains("--boxes")
args.removeAll { $0 == "--boxes" }
if args.isEmpty {
    FileHandle.standardError.write("usage: sa_ocr [--boxes] <image> [image ...]\n".data(using: .utf8)!)
    exit(2)
}

for path in args {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        print("\(path)\t!! could not open")
        continue
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false      // UI labels are not prose; correction hurts
    req.recognitionLanguages = ["en-US", "ar-SA"]
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    do {
        try handler.perform([req])
        let obs = req.results ?? []
        if wantBoxes {
            // Vision's boundingBox is normalised with the origin at the BOTTOM-left.
            // Flip it to top-left pixels, which is what every drawing tool here expects.
            let W = CGFloat(cg.width), H = CGFloat(cg.height)
            let parts: [String] = obs.compactMap { o in
                guard let t = o.topCandidates(1).first?.string else { return nil }
                let b = o.boundingBox
                let x = Int((b.minX * W).rounded())
                let y = Int(((1 - b.maxY) * H).rounded())
                let w = Int((b.width * W).rounded())
                let h = Int((b.height * H).rounded())
                return "\(t)@\(x),\(y),\(w),\(h)"
            }
            print("\(path)\t\(parts.joined(separator: " | "))")
        } else {
            let lines = obs.compactMap { $0.topCandidates(1).first?.string }
            print("\(path)\t\(lines.joined(separator: " | "))")
        }
    } catch {
        print("\(path)\t!! \(error.localizedDescription)")
    }
}
