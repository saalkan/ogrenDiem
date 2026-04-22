/**
 * MathView — auto-height WebView that renders LaTeX via KaTeX (CDN).
 *
 * The WebView measures its rendered content and posts the pixel height back.
 * Parent consumers place this inside a regular React Native ScrollView so
 * long questions scroll naturally as part of the page. No nested scrollers.
 *
 * Input: `content` is HTML that KaTeX auto-render will scan for $...$ and
 * $$...$$ delimiters. Escape user-supplied HTML before passing in.
 */
import React, { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { WebView } from 'react-native-webview';

const KATEX_CSS = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css';
const KATEX_JS = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js';
const AUTO = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js';

function buildHtml(content: string): string {
  return `<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <link rel="stylesheet" href="${KATEX_CSS}"/>
  <script src="${KATEX_JS}"></script>
  <script src="${AUTO}"></script>
  <style>
    html, body {
      margin: 0; padding: 0;
      background: transparent;
      color: #e6edf3;
      font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    #content { padding: 2px 2px 8px 2px; }
    .katex { font-size: 1.05em; }
    p { margin: 0 0 8px 0; }
    ol, ul { padding-left: 20px; margin: 4px 0 10px 0; }
    li { margin: 3px 0; }
    code {
      background: #1b2129; padding: 1px 4px; border-radius: 3px;
      font-family: ui-monospace, Menlo, Consolas, monospace;
    }
    .answer {
      margin-top: 6px; padding: 8px 10px;
      background: rgba(116, 185, 255, 0.08);
      border-left: 3px solid #74b9ff;
      border-radius: 4px;
    }
  </style>
</head>
<body>
<div id="content">${content}</div>
<script>
  function postHeight() {
    const h = document.getElementById('content').getBoundingClientRect().height;
    window.ReactNativeWebView.postMessage(String(Math.ceil(h)));
  }
  document.addEventListener('DOMContentLoaded', function () {
    renderMathInElement(document.body, {
      delimiters: [
        { left: '$$', right: '$$', display: true },
        { left: '$',  right: '$',  display: false }
      ],
      throwOnError: false
    });
    // Give fonts a tick to settle.
    setTimeout(postHeight, 60);
    setTimeout(postHeight, 250);
    window.addEventListener('resize', postHeight);
  });
</script>
</body>
</html>`;
}

interface Props {
  content: string;    // HTML with $...$ / $$...$$
  style?: any;
}

export const MathView: React.FC<Props> = ({ content, style }) => {
  const [height, setHeight] = useState(40);
  const webRef = useRef<WebView>(null);

  return (
    <View style={[{ height }, style]} pointerEvents="none">
      <WebView
        ref={webRef}
        originWhitelist={['*']}
        source={{ html: buildHtml(content) }}
        style={styles.web}
        scrollEnabled={false}
        showsVerticalScrollIndicator={false}
        javaScriptEnabled
        domStorageEnabled
        androidLayerType="hardware"
        backgroundColor="transparent"
        onMessage={(e) => {
          const h = parseInt(e.nativeEvent.data, 10);
          if (!isNaN(h) && h > 0 && Math.abs(h - height) > 1) setHeight(h);
        }}
      />
    </View>
  );
};

const styles = StyleSheet.create({
  web: { backgroundColor: 'transparent', flex: 1 },
});
