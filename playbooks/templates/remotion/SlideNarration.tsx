// Slide narration template: still slides, one voice-over line per slide, a gentle push-in
// on each still and a closing end card. Durations come from the scene list.
import React from "react";
import {
  AbsoluteFill, Audio, Img, Sequence, interpolate, staticFile, useCurrentFrame,
} from "remotion";
import scenes from "./scenes.example.json"; // [{ slide, vo, sec }] - swap in your own list

const GREEN = "#2E7D32";
const DARK = "#1B3A4B";
const FPS = 30;
const PAD = 0.7;           // air after each VO line (mode-B pacing)
const ENDCARD_SEC = 5;

export const totalFrames =
  scenes.reduce((a: number, s: any) => a + Math.round((s.sec + PAD) * FPS), 0) +
  ENDCARD_SEC * FPS;

const KenBurns: React.FC<{ src: string; frames: number }> = ({ src, frames }) => {
  const f = useCurrentFrame();
  // gentle 1.00 -> 1.04 push-in so stills feel alive (Powtoon-mode subtlety)
  const scale = interpolate(f, [0, frames], [1.0, 1.04]);
  const opacity = interpolate(f, [0, 10, frames - 10, frames], [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{ opacity, background: "#fff" }}>
      <Img src={staticFile(src)}
           style={{ width: "100%", height: "100%", objectFit: "contain",
                    transform: `scale(${scale})` }} />
    </AbsoluteFill>
  );
};

const EndCard: React.FC = () => {
  const f = useCurrentFrame();
  const opacity = interpolate(f, [0, 15], [0, 1], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill style={{
      background: `linear-gradient(135deg, ${DARK}, #0f2530)`, opacity,
      justifyContent: "center", alignItems: "center", color: "#fff",
      fontFamily: "Helvetica Neue, Arial, sans-serif",
    }}>
      <div style={{ width: 90, height: 6, background: GREEN, marginBottom: 32 }} />
      <div style={{ fontSize: 88, fontWeight: 800 }}>YOUR COMPANY</div>
      <div style={{ fontSize: 34, marginTop: 18, color: "#d6e4ea" }}>
        Your closing line here
      </div>
    </AbsoluteFill>
  );
};

export const SlideNarration: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {scenes.map((s: any, i: number) => {
        const dur = Math.round((s.sec + PAD) * FPS);
        const from = at; at += dur;
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <KenBurns src={s.slide} frames={dur} />
            <Audio src={staticFile(s.vo)} />
          </Sequence>
        );
      })}
      <Sequence from={at} durationInFrames={ENDCARD_SEC * FPS}>
        <EndCard />
      </Sequence>
    </AbsoluteFill>
  );
};
