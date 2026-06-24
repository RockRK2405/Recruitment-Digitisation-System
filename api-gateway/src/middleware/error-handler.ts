import { Request, Response, NextFunction } from 'express'

export class AppError extends Error {
  constructor(
    public statusCode: number,
    public message: string,
    public code: string = 'INTERNAL_ERROR'
  ) {
    super(message)
    this.name = 'AppError'
  }
}

export function errorHandler(err: Error, _req: Request, res: Response, _next: NextFunction) {
  if (err instanceof AppError) {
    return res.status(err.statusCode).json({
      message: err.message,
      code: err.code,
      status: err.statusCode,
    })
  }

  console.error('Unhandled error:', err)
  return res.status(500).json({
    message: 'Internal server error',
    code: 'INTERNAL_ERROR',
    status: 500,
  })
}

export function notFoundHandler(_req: Request, res: Response) {
  res.status(404).json({
    message: 'Resource not found',
    code: 'NOT_FOUND',
    status: 404,
  })
}
