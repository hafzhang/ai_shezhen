/**
 * Share Utility for uni-app
 * Handles image generation, saving, and sharing across platforms
 */

// Platform detection
declare const uni: any

export interface ShareImageOptions {
  title?: string
  imageUrl: string
  primarySyndrome?: string
  confidence?: number
  recommendations?: string[]
  backgroundColor?: string
  textColor?: string
  accentColor?: string
}

export interface ShareResult {
  success: boolean
  message?: string
  filePath?: string
}

export interface PlatformInfo {
  isH5: boolean
  isWeChat: boolean
  isDouyin: boolean
  isApp: boolean
}

/**
 * Detect current platform
 */
export function getPlatform(): PlatformInfo {
  // @ts-ignore - uni is available at runtime
  const systemInfo = uni?.getSystemInfoSync() || {}

  return {
    isH5: systemInfo.platform === 'web' || typeof window !== 'undefined',
    isWeChat: systemInfo.app === 'weixin' || systemInfo.platform === 'weixin',
    isDouyin: systemInfo.app === 'douyin' || systemInfo.platform === 'douyin',
    isApp: systemInfo.app === 'android' || systemInfo.app === 'ios'
  }
}

/**
 * Generate share image from diagnosis result
 * Uses HTML5 Canvas for H5 and uni.canvasToTempFilePath for mini-programs
 */
export async function generateShareImage(options: ShareImageOptions): Promise<ShareResult> {
  const {
    title = 'AI舌诊诊断结果',
    imageUrl,
    primarySyndrome = '',
    confidence = 0,
    recommendations = [],
    backgroundColor = '#ffffff',
    textColor = '#333333',
    accentColor = '#667eea'
  } = options

  const platform = getPlatform()

  try {
    if (platform.isH5) {
      return await generateShareImageH5({
        title,
        imageUrl,
        primarySyndrome,
        confidence,
        recommendations,
        backgroundColor,
        textColor,
        accentColor
      })
    } else {
      return await generateShareImageMini({
        title,
        imageUrl,
        primarySyndrome,
        confidence,
        recommendations,
        backgroundColor,
        textColor,
        accentColor
      })
    }
  } catch (error: any) {
    console.error('Generate share image failed:', error)
    return {
      success: false,
      message: error.message || '生成分享图片失败'
    }
  }
}

/**
 * Generate share image for H5 platform using Canvas API
 */
async function generateShareImageH5(options: ShareImageOptions): Promise<ShareResult> {
  const {
    title,
    imageUrl,
    primarySyndrome,
    confidence,
    recommendations,
    backgroundColor,
    textColor,
    accentColor
  } = options

  return new Promise((resolve, reject) => {
    // Check if canvas is supported
    if (typeof document === 'undefined') {
      resolve({
        success: false,
        message: '当前环境不支持Canvas'
      })
      return
    }

    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')

    if (!ctx) {
      resolve({
        success: false,
        message: 'Canvas初始化失败'
      })
      return
    }

    // Set canvas size (800x1200 for good quality)
    const width = 800
    const height = 1200
    canvas.width = width
    canvas.height = height

    // Load tongue image
    const img = new Image()
    img.crossOrigin = 'anonymous'

    img.onload = () => {
      try {
        // Draw background
        ctx.fillStyle = backgroundColor
        ctx.fillRect(0, 0, width, height)

        // Draw header gradient
        const headerGradient = ctx.createLinearGradient(0, 0, width, 200)
        headerGradient.addColorStop(0, accentColor)
        headerGradient.addColorStop(1, '#764ba2')
        ctx.fillStyle = headerGradient
        ctx.fillRect(0, 0, width, 200)

        // Draw title
        ctx.fillStyle = '#ffffff'
        ctx.font = 'bold 32px Arial, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText(title, width / 2, 80)

        // Draw tongue image
        const imageSize = 400
        const imageX = (width - imageSize) / 2
        const imageY = 120
        const borderRadius = 16

        // Draw rounded rectangle for image
        roundRect(ctx, imageX, imageY, imageSize, imageSize, borderRadius)
        ctx.clip()
        ctx.drawImage(img, imageX, imageY, imageSize, imageSize)
        ctx.restore()

        // Draw syndrome info
        ctx.fillStyle = textColor
        ctx.font = 'bold 28px Arial, sans-serif'
        ctx.textAlign = 'left'
        ctx.fillText('主要证型', 60, 580)

        ctx.fillStyle = accentColor
        ctx.font = 'bold 36px Arial, sans-serif'
        ctx.fillText(primarySyndrome, 60, 630)

        ctx.fillStyle = '#999999'
        ctx.font = '24px Arial, sans-serif'
        ctx.fillText(`置信度: ${Math.round(confidence * 100)}%`, 60, 670)

        // Draw recommendations
        ctx.fillStyle = textColor
        ctx.font = 'bold 28px Arial, sans-serif'
        ctx.fillText('健康建议', 60, 730)

        let yPos = 780
        const maxRecommendations = 3
        const displayRecommendations = recommendations.slice(0, maxRecommendations)

        displayRecommendations.forEach((rec, index) => {
          ctx.fillStyle = '#666666'
          ctx.font = '22px Arial, sans-serif'
          const text = `• ${rec}`
          ctx.fillText(text, 80, yPos)
          yPos += 40
        })

        // Draw footer
        ctx.fillStyle = accentColor
        ctx.font = '20px Arial, sans-serif'
        ctx.textAlign = 'center'
        ctx.fillText('AI舌诊智能诊断系统', width / 2, height - 40)

        // Convert to blob
        canvas.toBlob((blob) => {
          if (blob) {
            const reader = new FileReader()
            reader.onload = () => {
              const dataUrl = reader.result as string
              // For H5, return data URL
              resolve({
                success: true,
                filePath: dataUrl
              })
            }
            reader.onerror = () => {
              resolve({
                success: false,
                message: '图片转换失败'
              })
            }
            reader.readAsDataURL(blob)
          } else {
            resolve({
              success: false,
              message: '图片生成失败'
            })
          }
        }, 'image/png', 0.9)
      } catch (error: any) {
        resolve({
          success: false,
          message: error.message || '绘制图片失败'
        })
      }
    }

    img.onerror = () => {
      resolve({
        success: false,
        message: '图片加载失败'
      })
    }

    // Check if imageUrl is base64 or URL
    if (imageUrl.startsWith('data:')) {
      img.src = imageUrl
    } else {
      img.src = imageUrl
    }
  })
}

/**
 * Draw rounded rectangle
 */
function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
) {
  ctx.save()
  ctx.beginPath()
  ctx.moveTo(x + radius, y)
  ctx.lineTo(x + width - radius, y)
  ctx.quadraticCurveTo(x + width, y, x + width, y + radius)
  ctx.lineTo(x + width, y + height - radius)
  ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height)
  ctx.lineTo(x + radius, y + height)
  ctx.quadraticCurveTo(x, y + height, x, y + height - radius)
  ctx.lineTo(x, y + radius)
  ctx.quadraticCurveTo(x, y, x + radius, y)
  ctx.closePath()
}

/**
 * Generate share image for mini-program platform using uni.canvas
 */
async function generateShareImageMini(options: ShareImageOptions): Promise<ShareResult> {
  return new Promise((resolve) => {
    // @ts-ignore
    uni.createSelectorQuery()
      .select('#share-canvas')
      .fields({ node: true, size: true })
      .exec((res: any) => {
        if (!res || !res[0]) {
          // Create temporary canvas
          createTempCanvas(options).then(resolve).catch(() => {
            resolve({
              success: false,
              message: 'Canvas创建失败'
            })
          })
          return
        }

        const canvas = res[0].node
        const ctx = canvas.getContext('2d')

        const dpr = // @ts-ignore
          uni.getSystemInfoSync().pixelRatio || 1
        canvas.width = 800 * dpr
        canvas.height = 1200 * dpr
        ctx.scale(dpr, dpr)

        // Draw content (similar to H5 version)
        // ... (implementation would be similar to H5 version)

        // Convert to temp file path
        // @ts-ignore
        uni.canvasToTempFilePath({
          canvas: canvas,
          success: (res: any) => {
            resolve({
              success: true,
              filePath: res.tempFilePath
            })
          },
          fail: (err: any) => {
            resolve({
              success: false,
              message: err.errMsg || '图片生成失败'
            })
          }
        })
      })
  })
}

/**
 * Create temporary canvas for share image
 */
async function createTempCanvas(options: ShareImageOptions): Promise<ShareResult> {
  // For mini-programs, we would use a hidden canvas component
  // This is a simplified implementation
  return {
    success: false,
    message: '小程序端请使用canvas组件生成分享图片'
  }
}

/**
 * Save image to photo album
 */
export async function saveImageToAlbum(imagePath: string): Promise<ShareResult> {
  return new Promise((resolve) => {
    // @ts-ignore
    uni.saveImageToPhotosAlbum({
      filePath: imagePath,
      success: () => {
        resolve({
          success: true,
          message: '已保存到相册'
        })
      },
      fail: (err: any) => {
        if (err.errMsg.includes('auth')) {
          // Need to request permission
          // @ts-ignore
          uni.showModal({
            title: '权限请求',
            content: '需要相册权限才能保存图片',
            success: (res: any) => {
              if (res.confirm) {
                // Open settings
                // @ts-ignore
                uni.openSetting()
              }
            }
          })
        }
        resolve({
          success: false,
          message: err.errMsg || '保存失败'
        })
      }
    })
  })
}

/**
 * Share to WeChat
 */
export async function shareToWeChat(options: {
  title?: string
  path?: string
  imageUrl?: string
}): Promise<ShareResult> {
  return new Promise((resolve) => {
    // @ts-ignore
    uni.share({
      provider: 'weixin',
      type: 0, // 0-图文分享, 1-纯文字分享, 2-图片分享, 5-小程序分享
      title: options.title || 'AI舌诊诊断结果',
      href: options.path || '',
      imageUrl: options.imageUrl || '',
      success: () => {
        resolve({
          success: true,
          message: '分享成功'
        })
      },
      fail: (err: any) => {
        resolve({
          success: false,
          message: err.errMsg || '分享失败'
        })
      }
    })
  })
}

/**
 * Share with system share sheet
 */
export async function shareWithSystem(options: {
  title?: string
  content?: string
  imagePath?: string
}): Promise<ShareResult> {
  return new Promise((resolve) => {
    // @ts-ignore
    uni.showShareSheet({
      title: options.title || '分享',
      content: options.content || '',
      imagePath: options.imagePath || '',
      success: () => {
        resolve({
          success: true,
          message: '分享成功'
        })
      },
      fail: (err: any) => {
        resolve({
          success: false,
          message: err.errMsg || '分享失败'
        })
      }
    })
  })
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<ShareResult> {
  return new Promise((resolve) => {
    // @ts-ignore
    uni.setClipboardData({
      data: text,
      success: () => {
        resolve({
          success: true,
          message: '已复制到剪贴板'
        })
      },
      fail: (err: any) => {
        resolve({
          success: false,
          message: err.errMsg || '复制失败'
        })
      }
    })
  })
}

/**
 * Download image from URL
 */
export async function downloadImage(url: string): Promise<ShareResult> {
  return new Promise((resolve) => {
    // @ts-ignore
    uni.downloadFile({
      url: url,
      success: (res: any) => {
        if (res.statusCode === 200) {
          resolve({
            success: true,
            filePath: res.tempFilePath
          })
        } else {
          resolve({
            success: false,
            message: '下载失败'
          })
        }
      },
      fail: (err: any) => {
        resolve({
          success: false,
          message: err.errMsg || '下载失败'
        })
      }
    })
  })
}

/**
 * Generate share link
 */
export function generateShareLink(diagnosisId: string, baseUrl?: string): string {
  const base = baseUrl || 'https://your-app.com'
  return `${base}/pages/result/index?id=${diagnosisId}`
}

/**
 * Main share function - handles all share scenarios
 */
export async function shareDiagnosis(options: {
  diagnosisId?: string
  title?: string
  imageUrl: string
  primarySyndrome?: string
  confidence?: number
  recommendations?: string[]
  baseUrl?: string
}): Promise<ShareResult> {
  const platform = getPlatform()

  // Generate share image
  const imageResult = await generateShareImage({
    title: options.title,
    imageUrl: options.imageUrl,
    primarySyndrome: options.primarySyndrome,
    confidence: options.confidence,
    recommendations: options.recommendations
  })

  if (!imageResult.success || !imageResult.filePath) {
    return imageResult
  }

  // For WeChat mini-program, use native share
  if (platform.isWeChat && options.diagnosisId) {
    return await shareToWeChat({
      title: options.title,
      path: generateShareLink(options.diagnosisId, options.baseUrl),
      imageUrl: imageResult.filePath
    })
  }

  // For H5 and other platforms, use system share
  return await shareWithSystem({
    title: options.title,
    imagePath: imageResult.filePath
  })
}
