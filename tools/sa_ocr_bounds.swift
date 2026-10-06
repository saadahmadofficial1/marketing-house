// Local text geometry for pilot verification (done by codex).
import Foundation
import Vision
import AppKit
for path in CommandLine.arguments.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect:nil, context:nil, hints:nil) else { exit(2) }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = .accurate
    req.usesLanguageCorrection = false
    req.recognitionLanguages = ["en-US"]
    do {
        try VNImageRequestHandler(cgImage:cg, options:[:]).perform([req])
        let rows: [[String:Any]] = (req.results ?? []).compactMap { o in
            guard let c = o.topCandidates(1).first else { return nil }
            let b = o.boundingBox
            return ["text":c.string, "confidence":c.confidence,
                    "box":[b.minX*Double(cg.width), (1-b.maxY)*Double(cg.height),
                           b.width*Double(cg.width), b.height*Double(cg.height)]]
        }
        let data = try JSONSerialization.data(withJSONObject:["path":path,"width":cg.width,"height":cg.height,"rows":rows], options:[.sortedKeys])
        print(String(data:data,encoding:.utf8)!)
    } catch { fputs("OCR failed: \(error)\n",stderr); exit(1) }
}
