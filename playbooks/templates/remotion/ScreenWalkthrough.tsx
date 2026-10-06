import React from "react";
import {
  AbsoluteFill,
  Audio,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";

// Brand colours: placeholders, swap in your own
const GREEN = "#2E7D32";
const DARK = "#1B3A4B";
const FPS = 30;

type Scene = {
  vo: string;          // audio file in public/walkthrough/
  voSec: number;       // VO duration
  title: string;       // lower-third / card title
  caption: string;     // subtitle line (bottom)
  srcStart?: number;   // seconds into rec.mov; undefined = brand card scene
  bullets?: string[];  // extra lines on card scenes
};

export const SCENES: Scene[] = [
  { vo: "01.mp3", voSec: 8.3, title: "Request Portal — Quick & Easy",
    caption: "Raising a request has never been easier. Let's walk through it.",
    srcStart: 160 },
  { vo: "02.mp3", voSec: 5.5, title: "Step 1: Sign in to the portal",
    caption: "Start by signing in to the portal with your work account." },
  { vo: "03.mp3", voSec: 7.1, title: "Step 2: Open the request module",
    caption: "From the sidebar, select “Requests”, then choose the right category." },
  { vo: "04.mp3", voSec: 6.4, title: "Step 3: Create a request",
    caption: "Select “Create” and complete the required details.",
    srcStart: 15,
    bullets: ["Subject", "Description", "Department", "Category", "Attach Files"] },
  { vo: "05.mp3", voSec: 5.5, title: "Step 4: Submit",
    caption: "Click “Submit”. Your request is created instantly.", srcStart: 73 },
  { vo: "06.mp3", voSec: 5.9, title: "Track Progress",
    caption: "Track your request at any time from the list view.", srcStart: 80 },
  { vo: "07.mp3", voSec: 8.0, title: "Efficient • Simple • Transparent",
    caption: "Everything you need to manage your requests, all in one place.",
    srcStart: 160 },
];

const PAD = 0.6; // seconds of air after each VO line
export const sceneFrames = (s: Scene) => Math.round((s.voSec + PAD) * FPS);
export const totalFrames = SCENES.reduce((a, s) => a + sceneFrames(s), 0);

const Fade: React.FC<{ children: React.ReactNode; frames: number }> = ({ children, frames }) => {
  const f = useCurrentFrame();
  const opacity = interpolate(f, [0, 12, frames - 12, frames], [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return <AbsoluteFill style={{ opacity }}>{children}</AbsoluteFill>;
};

const LowerThird: React.FC<{ text: string }> = ({ text }) => (
  <div style={{
    position: "absolute", top: 64, left: 64, padding: "14px 28px",
    background: `${DARK}E6`, borderLeft: `6px solid ${GREEN}`, borderRadius: 10,
    color: "#fff", fontSize: 40, fontWeight: 700,
    fontFamily: "Avenir Next, -apple-system, sans-serif",
  }}>{text}</div>
);

const Caption: React.FC<{ text: string }> = ({ text }) => (
  <div style={{
    position: "absolute", bottom: 56, left: 0, right: 0, textAlign: "center",
  }}>
    <span style={{
      background: "rgba(0,0,0,0.72)", color: "#fff", padding: "10px 22px",
      borderRadius: 8, fontSize: 32, fontFamily: "Avenir Next, sans-serif",
    }}>{text}</span>
  </div>
);

// Full-screen brand card for scenes with no matching footage (login / navigate)
const BrandCard: React.FC<{ s: Scene }> = ({ s }) => (
  <AbsoluteFill style={{
    background: `linear-gradient(135deg, ${DARK} 0%, #10242f 100%)`,
    justifyContent: "center", alignItems: "center",
    fontFamily: "Avenir Next, sans-serif", color: "#fff",
  }}>
    <div style={{ width: 90, height: 6, background: GREEN, marginBottom: 36 }} />
    <div style={{ fontSize: 72, fontWeight: 800, textAlign: "center", maxWidth: 1300 }}>
      {s.title}
    </div>
    {s.bullets && (
      <div style={{ marginTop: 40, fontSize: 40, lineHeight: 1.7, color: "#dbe4ea" }}>
        {s.bullets.map((b) => (<div key={b}>✓ {b}</div>))}
      </div>
    )}
  </AbsoluteFill>
);

export const ScreenWalkthrough: React.FC = () => {
  let at = 0;
  return (
    <AbsoluteFill style={{ background: "#000" }}>
      {SCENES.map((s, i) => {
        const dur = sceneFrames(s);
        const from = at;
        at += dur;
        return (
          <Sequence key={i} from={from} durationInFrames={dur}>
            <Fade frames={dur}>
              {s.srcStart !== undefined ? (
                <>
                  {/* 112% scale hides the test-env URL bar */}
                  <AbsoluteFill style={{ transform: "scale(1.12)" }}>
                    <OffthreadVideo
                      src={staticFile("walkthrough/rec.mov")}
                      startFrom={Math.round(s.srcStart * FPS)}
                      muted
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
                  </AbsoluteFill>
                  <LowerThird text={s.title} />
                </>
              ) : (
                <BrandCard s={s} />
              )}
              <Caption text={s.caption} />
            </Fade>
            <Audio src={staticFile(`walkthrough/${s.vo}`)} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
