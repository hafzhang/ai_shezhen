/**
 * Image compression utility using canvas
 * Supports both uni-app (canvas 2d) and H5 (canvas API)
 */

// Declare uni global for TypeScript
declare const uni: any

export interface CompressOptions {
  /** Target quality (0.1 - 1.0), default 0.8 */
  quality?: number
  /** Maximum width in pixels, default 1920 */
  maxWidth?: number
  /** Maximum height in pixels, default 1920 */
  maxHeight?: number
  /** Target file size in bytes (approximate), default 2MB */
  maxFileSize?: number
  /** Output format, default 'jpeg' */
  format?: 'jpeg' | 'png'
}

export interface CompressResult {
  /** Compressed image as base64 data URL */
  dataUrl: string
  /** Original file size in bytes */
  originalSize: number
  /** Compressed file size in bytes */
  compressedSize: number
  /** Compression ratio (0-1) */
  ratio: number
  /** Image dimensions */
  width: number
  height: number
}

/**
 * Check if running in H5 environment
 */
function isH5(): boolean {
  try {
    return typeof uni !== 'undefined' && uni.getSystemInfoSync().platform === 'web'
  } catch {
    return false
  }
}

/**
 * Calculate target dimensions maintaining aspect ratio
 */
function calculateDimensions(
  originalWidth: number,
  originalHeight: number,
  maxWidth: number,
  maxHeight: number
): { width: number; height: number } {
  let width = originalWidth
  let height = originalHeight

  // Scale down if exceeds max dimensions
  if (width > maxWidth || height > maxHeight) {
    const widthRatio = maxWidth / width
    const heightRatio = maxHeight / height
    const ratio = Math.min(widthRatio, heightRatio)
    width = Math.floor(width * ratio)
    height = Math.floor(height * ratio)
  }

  return { width, height }
}

/**
 * Get image info from file path
 */
function getImageInfo(filePath: string): Promise<any> {
  return new Promise((resolve, reject) => {
    uni.getImageInfo({
      src: filePath,
      success: resolve,
      fail: reject
    })
  })
}

/**
 * Compress image using canvas (H5)
 */
async function compressImageH5(
  imagePath: string,
  options: Required<CompressOptions>
): Promise<CompressResult> {
  return new Promise((resolve, reject) => {
    if (typeof document === 'undefined' || typeof Image === 'undefined') {
      reject(new Error('Browser API not available'))
      return
    }

    const img = new Image()
    img.crossOrigin = 'anonymous'

    img.onload = () => {
      try {
        // Calculate target dimensions
        const { width, height } = calculateDimensions(
          img.width,
          img.height,
          options.maxWidth,
          options.maxHeight
        )

        // Create canvas
        const canvas = document.createElement('canvas')
        canvas.width = width
        canvas.height = height

        const ctx = canvas.getContext('2d')
        if (!ctx) {
          reject(new Error('Failed to get canvas context'))
          return
        }

        // Draw image on canvas
        ctx.fillStyle = '#FFFFFF'
        ctx.fillRect(0, 0, width, height)
        ctx.drawImage(img, 0, 0, width, height)

        // Export as base64 with quality
        const mimeType = options.format === 'png' ? 'image/png' : 'image/jpeg'
        let quality = options.quality

        // Iteratively reduce quality if file size is too large
        let dataUrl = canvas.toDataURL(mimeType, quality)
        const base64Prefix = `data:${mimeType};base64,`
        let compressedSize = Math.floor((dataUrl.length - base64Prefix.length) * 0.75)

        // Reduce quality iteratively if file size exceeds max
        while (compressedSize > options.maxFileSize && quality > 0.1) {
          quality -= 0.1
          dataUrl = canvas.toDataURL(mimeType, quality)
          compressedSize = Math.floor((dataUrl.length - base64Prefix.length) * 0.75)
        }

        // Get original size (approximate)
        const originalSize = Math.round(compressedSize / quality)

        resolve({
          dataUrl,
          originalSize,
          compressedSize,
          ratio: compressedSize / originalSize,
          width,
          height
        })
      } catch (error) {
        reject(error)
      }
    }

    img.onerror = () => {
      reject(new Error('Failed to load image'))
    }

    img.src = imagePath
  })
}

/**
 * Compress image using canvas (uni-app)
 */
async function compressImageUniApp(
  imagePath: string,
  options: Required<CompressOptions>
): Promise<CompressResult> {
  return new Promise(async (resolve, reject) => {
    try {
      // Get image info
      const imageInfo = await getImageInfo(imagePath)

      // Calculate target dimensions
      const { width, height } = calculateDimensions(
        imageInfo.width,
        imageInfo.height,
        options.maxWidth,
        options.maxHeight
      )

      // For mini-programs, use uni.canvasToTempFilePath for compression
      uni.canvasToTempFilePath({
        canvasId: 'compressCanvas',
        x: 0,
        y: 0,
        width: imageInfo.width,
        height: imageInfo.height,
        destWidth: width,
        destHeight: height,
        fileType: options.format === 'png' ? 'png' : 'jpg',
        quality: options.quality * 100,
        success: (res: any) => {
          // Read compressed file and convert to base64
          uni.getFileSystemManager().readFile({
            filePath: res.tempFilePath,
            encoding: 'base64',
            success: (fileRes: any) => {
              const dataUrl = `data:image/${options.format === 'png' ? 'png' : 'jpeg'};base64,${fileRes.data}`
              const compressedSize = Math.floor(fileRes.data.length * 0.75)
              const originalSize = Math.round(compressedSize / options.quality)

              resolve({
                dataUrl,
                originalSize,
                compressedSize,
                ratio: compressedSize / originalSize,
                width,
                height
              })
            },
            fail: reject
          })
        },
        fail: reject
      })
    } catch (error) {
      reject(error)
    }
  })
}

/**
 * Compress image from file path
 */
export async function compressImage(
  filePath: string,
  options: CompressOptions = {}
): Promise<CompressResult> {
  const defaultOptions: Required<CompressOptions> = {
    quality: options.quality ?? 0.8,
    maxWidth: options.maxWidth ?? 1920,
    maxHeight: options.maxHeight ?? 1920,
    maxFileSize: options.maxFileSize ?? 2 * 1024 * 1024, // 2MB
    format: options.format ?? 'jpeg'
  }

  try {
    if (isH5()) {
      // For H5, use browser canvas API
      return await compressImageH5(filePath, defaultOptions)
    } else {
      // For mini-programs, use uni-app canvas API
      return await compressImageUniApp(filePath, defaultOptions)
    }
  } catch (error) {
    console.error('Image compression failed:', error)
    // Fallback: return original image as base64
    return new Promise((resolve, reject) => {
      try {
        uni.getFileSystemManager().readFile({
          filePath,
          encoding: 'base64',
          success: (res: any) => {
            const dataUrl = `data:image/jpeg;base64,${res.data}`
            const size = Math.floor(res.data.length * 0.75)
            resolve({
              dataUrl,
              originalSize: size,
              compressedSize: size,
              ratio: 1,
              width: 0,
              height: 0
            })
          },
          fail: reject
        })
      } catch (e) {
        reject(e)
      }
    })
  }
}

/**
 * Compress image from base64 data URL
 */
export async function compressImageFromBase64(
  base64: string,
  options: CompressOptions = {}
): Promise<CompressResult> {
  // Extract base64 data
  const matches = base64.match(/^data:image\/(\w+);base64,(.+)$/)
  if (!matches) {
    throw new Error('Invalid base64 image format')
  }

  const format = matches[1] as 'jpeg' | 'png' | 'jpg' | 'webp'
  const data = matches[2]

  // For H5, create a blob and use compressImage
  if (isH5() && typeof atob !== 'undefined' && typeof Blob !== 'undefined') {
    try {
      // Convert base64 to blob
      const byteCharacters = atob(data)
      const byteNumbers = new Array(byteCharacters.length)
      for (let i = 0; i < byteCharacters.length; i++) {
        byteNumbers[i] = byteCharacters.charCodeAt(i)
      }
      const byteArray = new Uint8Array(byteNumbers)
      const blob = new Blob([byteArray], { type: `image/${format}` })
      const url = URL.createObjectURL(blob)

      const result = await compressImageH5(url, {
        quality: options.quality ?? 0.8,
        maxWidth: options.maxWidth ?? 1920,
        maxHeight: options.maxHeight ?? 1920,
        maxFileSize: options.maxFileSize ?? 2 * 1024 * 1024,
        format: format === 'png' ? 'png' : 'jpeg'
      })
      URL.revokeObjectURL(url)
      return result
    } catch (error) {
      console.error('H5 compression from base64 failed:', error)
      throw error
    }
  }

  // For mini-programs, save to temp file and compress
  return new Promise((resolve, reject) => {
    try {
      const tempPath = `${uni.env.USER_DATA_PATH}/temp_${Date.now()}.${format === 'png' ? 'png' : 'jpg'}`

      uni.getFileSystemManager().writeFile({
        filePath: tempPath,
        data: data,
        encoding: 'base64',
        success: () => {
          compressImage(tempPath, {
            ...options,
            format: format === 'png' ? 'png' : 'jpeg'
          })
            .then(resolve)
            .catch(reject)
        },
        fail: reject
      })
    } catch (error) {
      reject(error)
    }
  })
}

/**
 * Format file size for display
 */
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) {
    return `${bytes} B`
  } else if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  } else {
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }
}

export default {
  compressImage,
  compressImageFromBase64,
  formatFileSize
}
