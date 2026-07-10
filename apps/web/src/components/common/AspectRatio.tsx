import { AspectRatio, AspectRatioImage, RATIOS } from '@/components/common/AspectRatio';

// Ratio carré (1:1)
<AspectRatio ratio={1}>
  <img src="/image.jpg" alt="Image" className="h-full w-full object-cover" />
</AspectRatio>

// Ratio vidéo (16:9)
<AspectRatio ratio={RATIOS.video}>
  <iframe
    src="https://www.youtube.com/embed/..."
    title="YouTube video"
    allowFullScreen
    className="absolute inset-0 h-full w-full"
  />
</AspectRatio>

// Image avec ratio et placeholder
<AspectRatioImage
  src="/image.jpg"
  alt="Description"
  ratio={RATIOS.instagram}
  objectFit="cover"
  placeholder="/placeholder.jpg"
  className="rounded-lg"
/>

// Vidéo avec ratio
<AspectRatioVideo
  src="/video.mp4"
  poster="/poster.jpg"
  ratio={RATIOS.video}
  controls
  autoPlay
  muted
/>

// Iframe avec ratio
<AspectRatioIframe
  src="https://www.youtube.com/embed/..."
  title="YouTube video"
  ratio={RATIOS.widescreen}
  allowFullScreen
/>

// Ratios prédéfinis disponibles:
// RATIOS.square       // 1:1
// RATIOS.video        // 16:9
// RATIOS.portrait     // 3:4
// RATIOS.landscape    // 4:3
// RATIOS.widescreen   // 21:9
// RATIOS.ultrawide    // 32:9
// RATIOS.golden       // 1.618
// RATIOS.cinema       // 2.39
// RATIOS.instagram    // 1:1
// RATIOS.instagramStory // 9:16
// RATIOS.facebook     // 1.91:1
// RATIOS.twitter      // 2:1
// RATIOS.linkedin     // 1.91:1
// RATIOS.youtube      // 16:9
// RATIOS.youtubeShorts // 9:16
// RATIOS.tiktok       // 9:16
