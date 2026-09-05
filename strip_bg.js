const sharp = require('sharp');
const path = require('path');

const INPUT  = path.join(__dirname, 'panah_backend', 'static', 'logo-icon.png');
const OUTPUT = path.join(__dirname, 'panah_backend', 'static', 'logo-icon-transparent.png');

(async () => {
  const img = sharp(INPUT);
  const { data, info } = await img.raw().toBuffer({ resolveWithObject: true });

  // Sample background color from the top-left 10x10 area for accuracy
  let rSum = 0, gSum = 0, bSum = 0, count = 0;
  for (let y = 0; y < 10; y++) {
    for (let x = 0; x < 10; x++) {
      const i = (y * info.width + x) * info.channels;
      rSum += data[i];
      gSum += data[i + 1];
      bSum += data[i + 2];
      count++;
    }
  }
  const bgR = Math.round(rSum / count);
  const bgG = Math.round(gSum / count);
  const bgB = Math.round(bSum / count);
  console.log(`Sampled background RGB: (${bgR}, ${bgG}, ${bgB})`);

  // Threshold: how close a pixel must be to the bg color to become transparent
  const THRESHOLD = 40;

  const out = Buffer.alloc(info.width * info.height * 4); // RGBA output

  for (let i = 0; i < info.width * info.height; i++) {
    const srcOff = i * info.channels;
    const dstOff = i * 4;
    const r = data[srcOff];
    const g = data[srcOff + 1];
    const b = data[srcOff + 2];

    // Euclidean distance from the sampled background color
    const dist = Math.sqrt((r - bgR) ** 2 + (g - bgG) ** 2 + (b - bgB) ** 2);

    out[dstOff]     = r;
    out[dstOff + 1] = g;
    out[dstOff + 2] = b;

    if (dist < THRESHOLD) {
      out[dstOff + 3] = 0; // fully transparent
    } else if (dist < THRESHOLD * 2) {
      // Feathered edge: partial transparency for smooth transition
      out[dstOff + 3] = Math.round(((dist - THRESHOLD) / THRESHOLD) * 255);
    } else {
      out[dstOff + 3] = 255; // fully opaque
    }
  }

  await sharp(out, {
    raw: { width: info.width, height: info.height, channels: 4 }
  })
  .png()
  .toFile(OUTPUT);

  console.log(`Saved transparent icon to: ${OUTPUT}`);
})();
