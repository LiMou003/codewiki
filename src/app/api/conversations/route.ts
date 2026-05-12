import { NextRequest, NextResponse } from 'next/server';

const TARGET_SERVER_BASE_URL = process.env.SERVER_BASE_URL || 'http://localhost:8001';

async function handleProxy(
  req: NextRequest,
  pathSegments: string[]
): Promise<NextResponse> {
  try {
    const queryString = req.nextUrl.search;
    const targetUrl = `${TARGET_SERVER_BASE_URL}/api/conversations/${pathSegments.join('/')}${queryString}`;

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    const authHeader = req.headers.get('authorization');
    if (authHeader) {
      headers['Authorization'] = authHeader;
    }

    const body = req.method !== 'GET' && req.method !== 'HEAD' ? await req.text() : undefined;

    const backendRes = await fetch(targetUrl, {
      method: req.method,
      headers,
      body,
    });

    const data = await backendRes.text();

    return new NextResponse(data, {
      status: backendRes.status,
      headers: {
        'Content-Type': backendRes.headers.get('Content-Type') || 'application/json',
      },
    });
  } catch (error) {
    console.error('Error in /api/conversations proxy:', error);
    return NextResponse.json(
      { error: 'Internal Server Error' },
      { status: 500 }
    );
  }
}

export async function GET(req: NextRequest) {
  return handleProxy(req, []);
}

export async function POST(req: NextRequest) {
  return handleProxy(req, []);
}

export async function DELETE(req: NextRequest) {
  return handleProxy(req, []);
}

export async function PUT(req: NextRequest) {
  return handleProxy(req, []);
}

export async function PATCH(req: NextRequest) {
  return handleProxy(req, []);
}
