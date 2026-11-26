(function(){const e=document.createElement("link").relList;if(e&&e.supports&&e.supports("modulepreload"))return;for(const r of document.querySelectorAll('link[rel="modulepreload"]'))n(r);new MutationObserver(r=>{for(const s of r)if(s.type==="childList")for(const a of s.addedNodes)a.tagName==="LINK"&&a.rel==="modulepreload"&&n(a)}).observe(document,{childList:!0,subtree:!0});function t(r){const s={};return r.integrity&&(s.integrity=r.integrity),r.referrerPolicy&&(s.referrerPolicy=r.referrerPolicy),r.crossOrigin==="use-credentials"?s.credentials="include":r.crossOrigin==="anonymous"?s.credentials="omit":s.credentials="same-origin",s}function n(r){if(r.ep)return;r.ep=!0;const s=t(r);fetch(r.href,s)}})();const Wl="179",pr={ROTATE:0,DOLLY:1,PAN:2},dr={ROTATE:0,PAN:1,DOLLY_PAN:2,DOLLY_ROTATE:3},nf=0,zc=1,rf=2,Eu=1,Tu=2,Wn=3,ei=0,jt=1,un=2,fi=0,mr=1,kc=2,Hc=3,Gc=4,sf=5,Ci=100,af=101,of=102,lf=103,cf=104,df=200,uf=201,hf=202,ff=203,jo=204,qo=205,pf=206,mf=207,gf=208,_f=209,yf=210,xf=211,vf=212,Mf=213,bf=214,Yo=0,Ko=1,$o=2,br=3,Zo=4,Jo=5,Qo=6,el=7,Xl=0,Sf=1,wf=2,pi=0,Ef=1,Tf=2,Af=3,Au=4,Rf=5,Cf=6,Pf=7,Vc="attached",If="detached",Ru=300,Sr=301,wr=302,La=303,tl=304,Va=306,_i=1e3,Cn=1001,Da=1002,qt=1003,Cu=1004,ts=1005,Tt=1006,xa=1007,Pn=1008,Sn=1009,Pu=1010,Iu=1011,hs=1012,jl=1013,Di=1014,$t=1015,In=1016,ql=1017,Yl=1018,fs=1020,Lu=35902,Du=1021,Nu=1022,sn=1023,ps=1026,ms=1027,Kl=1028,$l=1029,Uu=1030,Zl=1031,Jl=1033,va=33776,Ma=33777,ba=33778,Sa=33779,nl=35840,il=35841,rl=35842,sl=35843,al=36196,ol=37492,ll=37496,cl=37808,dl=37809,ul=37810,hl=37811,fl=37812,pl=37813,ml=37814,gl=37815,_l=37816,yl=37817,xl=37818,vl=37819,Ml=37820,bl=37821,wa=36492,Sl=36494,wl=36495,Fu=36283,El=36284,Tl=36285,Al=36286,gs=2300,_s=2301,no=2302,Wc=2400,Xc=2401,jc=2402,Lf=2500,Df=0,Ou=1,Rl=2,Nf=3200,Uf=3201,Ql=0,Ff=1,hi="",Et="srgb",zt="srgb-linear",Na="linear",lt="srgb",Hi=7680,qc=519,Of=512,Bf=513,zf=514,Bu=515,kf=516,Hf=517,Gf=518,Vf=519,Cl=35044,Yc="300 es",Ln=2e3,Ua=2001;class Oi{addEventListener(e,t){this._listeners===void 0&&(this._listeners={});const n=this._listeners;n[e]===void 0&&(n[e]=[]),n[e].indexOf(t)===-1&&n[e].push(t)}hasEventListener(e,t){const n=this._listeners;return n===void 0?!1:n[e]!==void 0&&n[e].indexOf(t)!==-1}removeEventListener(e,t){const n=this._listeners;if(n===void 0)return;const r=n[e];if(r!==void 0){const s=r.indexOf(t);s!==-1&&r.splice(s,1)}}dispatchEvent(e){const t=this._listeners;if(t===void 0)return;const n=t[e.type];if(n!==void 0){e.target=this;const r=n.slice(0);for(let s=0,a=r.length;s<a;s++)r[s].call(this,e);e.target=null}}}const Ut=["00","01","02","03","04","05","06","07","08","09","0a","0b","0c","0d","0e","0f","10","11","12","13","14","15","16","17","18","19","1a","1b","1c","1d","1e","1f","20","21","22","23","24","25","26","27","28","29","2a","2b","2c","2d","2e","2f","30","31","32","33","34","35","36","37","38","39","3a","3b","3c","3d","3e","3f","40","41","42","43","44","45","46","47","48","49","4a","4b","4c","4d","4e","4f","50","51","52","53","54","55","56","57","58","59","5a","5b","5c","5d","5e","5f","60","61","62","63","64","65","66","67","68","69","6a","6b","6c","6d","6e","6f","70","71","72","73","74","75","76","77","78","79","7a","7b","7c","7d","7e","7f","80","81","82","83","84","85","86","87","88","89","8a","8b","8c","8d","8e","8f","90","91","92","93","94","95","96","97","98","99","9a","9b","9c","9d","9e","9f","a0","a1","a2","a3","a4","a5","a6","a7","a8","a9","aa","ab","ac","ad","ae","af","b0","b1","b2","b3","b4","b5","b6","b7","b8","b9","ba","bb","bc","bd","be","bf","c0","c1","c2","c3","c4","c5","c6","c7","c8","c9","ca","cb","cc","cd","ce","cf","d0","d1","d2","d3","d4","d5","d6","d7","d8","d9","da","db","dc","dd","de","df","e0","e1","e2","e3","e4","e5","e6","e7","e8","e9","ea","eb","ec","ed","ee","ef","f0","f1","f2","f3","f4","f5","f6","f7","f8","f9","fa","fb","fc","fd","fe","ff"];let Kc=1234567;const gr=Math.PI/180,Er=180/Math.PI;function bn(){const i=Math.random()*4294967295|0,e=Math.random()*4294967295|0,t=Math.random()*4294967295|0,n=Math.random()*4294967295|0;return(Ut[i&255]+Ut[i>>8&255]+Ut[i>>16&255]+Ut[i>>24&255]+"-"+Ut[e&255]+Ut[e>>8&255]+"-"+Ut[e>>16&15|64]+Ut[e>>24&255]+"-"+Ut[t&63|128]+Ut[t>>8&255]+"-"+Ut[t>>16&255]+Ut[t>>24&255]+Ut[n&255]+Ut[n>>8&255]+Ut[n>>16&255]+Ut[n>>24&255]).toLowerCase()}function Xe(i,e,t){return Math.max(e,Math.min(t,i))}function ec(i,e){return(i%e+e)%e}function Wf(i,e,t,n,r){return n+(i-e)*(r-n)/(t-e)}function Xf(i,e,t){return i!==e?(t-i)/(e-i):0}function ls(i,e,t){return(1-t)*i+t*e}function jf(i,e,t,n){return ls(i,e,1-Math.exp(-t*n))}function qf(i,e=1){return e-Math.abs(ec(i,e*2)-e)}function Yf(i,e,t){return i<=e?0:i>=t?1:(i=(i-e)/(t-e),i*i*(3-2*i))}function Kf(i,e,t){return i<=e?0:i>=t?1:(i=(i-e)/(t-e),i*i*i*(i*(i*6-15)+10))}function $f(i,e){return i+Math.floor(Math.random()*(e-i+1))}function Zf(i,e){return i+Math.random()*(e-i)}function Jf(i){return i*(.5-Math.random())}function Qf(i){i!==void 0&&(Kc=i);let e=Kc+=1831565813;return e=Math.imul(e^e>>>15,e|1),e^=e+Math.imul(e^e>>>7,e|61),((e^e>>>14)>>>0)/4294967296}function ep(i){return i*gr}function tp(i){return i*Er}function np(i){return(i&i-1)===0&&i!==0}function ip(i){return Math.pow(2,Math.ceil(Math.log(i)/Math.LN2))}function rp(i){return Math.pow(2,Math.floor(Math.log(i)/Math.LN2))}function sp(i,e,t,n,r){const s=Math.cos,a=Math.sin,o=s(t/2),l=a(t/2),c=s((e+n)/2),h=a((e+n)/2),u=s((e-n)/2),f=a((e-n)/2),p=s((n-e)/2),_=a((n-e)/2);switch(r){case"XYX":i.set(o*h,l*u,l*f,o*c);break;case"YZY":i.set(l*f,o*h,l*u,o*c);break;case"ZXZ":i.set(l*u,l*f,o*h,o*c);break;case"XZX":i.set(o*h,l*_,l*p,o*c);break;case"YXY":i.set(l*p,o*h,l*_,o*c);break;case"ZYZ":i.set(l*_,l*p,o*h,o*c);break;default:console.warn("THREE.MathUtils: .setQuaternionFromProperEuler() encountered an unknown order: "+r)}}function vn(i,e){switch(e.constructor){case Float32Array:return i;case Uint32Array:return i/4294967295;case Uint16Array:return i/65535;case Uint8Array:return i/255;case Int32Array:return Math.max(i/2147483647,-1);case Int16Array:return Math.max(i/32767,-1);case Int8Array:return Math.max(i/127,-1);default:throw new Error("Invalid component type.")}}function st(i,e){switch(e.constructor){case Float32Array:return i;case Uint32Array:return Math.round(i*4294967295);case Uint16Array:return Math.round(i*65535);case Uint8Array:return Math.round(i*255);case Int32Array:return Math.round(i*2147483647);case Int16Array:return Math.round(i*32767);case Int8Array:return Math.round(i*127);default:throw new Error("Invalid component type.")}}const wn={DEG2RAD:gr,RAD2DEG:Er,generateUUID:bn,clamp:Xe,euclideanModulo:ec,mapLinear:Wf,inverseLerp:Xf,lerp:ls,damp:jf,pingpong:qf,smoothstep:Yf,smootherstep:Kf,randInt:$f,randFloat:Zf,randFloatSpread:Jf,seededRandom:Qf,degToRad:ep,radToDeg:tp,isPowerOfTwo:np,ceilPowerOfTwo:ip,floorPowerOfTwo:rp,setQuaternionFromProperEuler:sp,normalize:st,denormalize:vn};class xe{constructor(e=0,t=0){xe.prototype.isVector2=!0,this.x=e,this.y=t}get width(){return this.x}set width(e){this.x=e}get height(){return this.y}set height(e){this.y=e}set(e,t){return this.x=e,this.y=t,this}setScalar(e){return this.x=e,this.y=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y)}copy(e){return this.x=e.x,this.y=e.y,this}add(e){return this.x+=e.x,this.y+=e.y,this}addScalar(e){return this.x+=e,this.y+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this}subScalar(e){return this.x-=e,this.y-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this}multiply(e){return this.x*=e.x,this.y*=e.y,this}multiplyScalar(e){return this.x*=e,this.y*=e,this}divide(e){return this.x/=e.x,this.y/=e.y,this}divideScalar(e){return this.multiplyScalar(1/e)}applyMatrix3(e){const t=this.x,n=this.y,r=e.elements;return this.x=r[0]*t+r[3]*n+r[6],this.y=r[1]*t+r[4]*n+r[7],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this}clamp(e,t){return this.x=Xe(this.x,e.x,t.x),this.y=Xe(this.y,e.y,t.y),this}clampScalar(e,t){return this.x=Xe(this.x,e,t),this.y=Xe(this.y,e,t),this}clampLength(e,t){const n=this.length();return this.divideScalar(n||1).multiplyScalar(Xe(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this}negate(){return this.x=-this.x,this.y=-this.y,this}dot(e){return this.x*e.x+this.y*e.y}cross(e){return this.x*e.y-this.y*e.x}lengthSq(){return this.x*this.x+this.y*this.y}length(){return Math.sqrt(this.x*this.x+this.y*this.y)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)}normalize(){return this.divideScalar(this.length()||1)}angle(){return Math.atan2(-this.y,-this.x)+Math.PI}angleTo(e){const t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;const n=this.dot(e)/t;return Math.acos(Xe(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){const t=this.x-e.x,n=this.y-e.y;return t*t+n*n}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this}equals(e){return e.x===this.x&&e.y===this.y}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this}rotateAround(e,t){const n=Math.cos(t),r=Math.sin(t),s=this.x-e.x,a=this.y-e.y;return this.x=s*n-a*r+e.x,this.y=s*r+a*n+e.y,this}random(){return this.x=Math.random(),this.y=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y}}class En{constructor(e=0,t=0,n=0,r=1){this.isQuaternion=!0,this._x=e,this._y=t,this._z=n,this._w=r}static slerpFlat(e,t,n,r,s,a,o){let l=n[r+0],c=n[r+1],h=n[r+2],u=n[r+3];const f=s[a+0],p=s[a+1],_=s[a+2],y=s[a+3];if(o===0){e[t+0]=l,e[t+1]=c,e[t+2]=h,e[t+3]=u;return}if(o===1){e[t+0]=f,e[t+1]=p,e[t+2]=_,e[t+3]=y;return}if(u!==y||l!==f||c!==p||h!==_){let g=1-o;const m=l*f+c*p+h*_+u*y,E=m>=0?1:-1,w=1-m*m;if(w>Number.EPSILON){const T=Math.sqrt(w),L=Math.atan2(T,m*E);g=Math.sin(g*L)/T,o=Math.sin(o*L)/T}const x=o*E;if(l=l*g+f*x,c=c*g+p*x,h=h*g+_*x,u=u*g+y*x,g===1-o){const T=1/Math.sqrt(l*l+c*c+h*h+u*u);l*=T,c*=T,h*=T,u*=T}}e[t]=l,e[t+1]=c,e[t+2]=h,e[t+3]=u}static multiplyQuaternionsFlat(e,t,n,r,s,a){const o=n[r],l=n[r+1],c=n[r+2],h=n[r+3],u=s[a],f=s[a+1],p=s[a+2],_=s[a+3];return e[t]=o*_+h*u+l*p-c*f,e[t+1]=l*_+h*f+c*u-o*p,e[t+2]=c*_+h*p+o*f-l*u,e[t+3]=h*_-o*u-l*f-c*p,e}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get w(){return this._w}set w(e){this._w=e,this._onChangeCallback()}set(e,t,n,r){return this._x=e,this._y=t,this._z=n,this._w=r,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._w)}copy(e){return this._x=e.x,this._y=e.y,this._z=e.z,this._w=e.w,this._onChangeCallback(),this}setFromEuler(e,t=!0){const n=e._x,r=e._y,s=e._z,a=e._order,o=Math.cos,l=Math.sin,c=o(n/2),h=o(r/2),u=o(s/2),f=l(n/2),p=l(r/2),_=l(s/2);switch(a){case"XYZ":this._x=f*h*u+c*p*_,this._y=c*p*u-f*h*_,this._z=c*h*_+f*p*u,this._w=c*h*u-f*p*_;break;case"YXZ":this._x=f*h*u+c*p*_,this._y=c*p*u-f*h*_,this._z=c*h*_-f*p*u,this._w=c*h*u+f*p*_;break;case"ZXY":this._x=f*h*u-c*p*_,this._y=c*p*u+f*h*_,this._z=c*h*_+f*p*u,this._w=c*h*u-f*p*_;break;case"ZYX":this._x=f*h*u-c*p*_,this._y=c*p*u+f*h*_,this._z=c*h*_-f*p*u,this._w=c*h*u+f*p*_;break;case"YZX":this._x=f*h*u+c*p*_,this._y=c*p*u+f*h*_,this._z=c*h*_-f*p*u,this._w=c*h*u-f*p*_;break;case"XZY":this._x=f*h*u-c*p*_,this._y=c*p*u-f*h*_,this._z=c*h*_+f*p*u,this._w=c*h*u+f*p*_;break;default:console.warn("THREE.Quaternion: .setFromEuler() encountered an unknown order: "+a)}return t===!0&&this._onChangeCallback(),this}setFromAxisAngle(e,t){const n=t/2,r=Math.sin(n);return this._x=e.x*r,this._y=e.y*r,this._z=e.z*r,this._w=Math.cos(n),this._onChangeCallback(),this}setFromRotationMatrix(e){const t=e.elements,n=t[0],r=t[4],s=t[8],a=t[1],o=t[5],l=t[9],c=t[2],h=t[6],u=t[10],f=n+o+u;if(f>0){const p=.5/Math.sqrt(f+1);this._w=.25/p,this._x=(h-l)*p,this._y=(s-c)*p,this._z=(a-r)*p}else if(n>o&&n>u){const p=2*Math.sqrt(1+n-o-u);this._w=(h-l)/p,this._x=.25*p,this._y=(r+a)/p,this._z=(s+c)/p}else if(o>u){const p=2*Math.sqrt(1+o-n-u);this._w=(s-c)/p,this._x=(r+a)/p,this._y=.25*p,this._z=(l+h)/p}else{const p=2*Math.sqrt(1+u-n-o);this._w=(a-r)/p,this._x=(s+c)/p,this._y=(l+h)/p,this._z=.25*p}return this._onChangeCallback(),this}setFromUnitVectors(e,t){let n=e.dot(t)+1;return n<1e-8?(n=0,Math.abs(e.x)>Math.abs(e.z)?(this._x=-e.y,this._y=e.x,this._z=0,this._w=n):(this._x=0,this._y=-e.z,this._z=e.y,this._w=n)):(this._x=e.y*t.z-e.z*t.y,this._y=e.z*t.x-e.x*t.z,this._z=e.x*t.y-e.y*t.x,this._w=n),this.normalize()}angleTo(e){return 2*Math.acos(Math.abs(Xe(this.dot(e),-1,1)))}rotateTowards(e,t){const n=this.angleTo(e);if(n===0)return this;const r=Math.min(1,t/n);return this.slerp(e,r),this}identity(){return this.set(0,0,0,1)}invert(){return this.conjugate()}conjugate(){return this._x*=-1,this._y*=-1,this._z*=-1,this._onChangeCallback(),this}dot(e){return this._x*e._x+this._y*e._y+this._z*e._z+this._w*e._w}lengthSq(){return this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w}length(){return Math.sqrt(this._x*this._x+this._y*this._y+this._z*this._z+this._w*this._w)}normalize(){let e=this.length();return e===0?(this._x=0,this._y=0,this._z=0,this._w=1):(e=1/e,this._x=this._x*e,this._y=this._y*e,this._z=this._z*e,this._w=this._w*e),this._onChangeCallback(),this}multiply(e){return this.multiplyQuaternions(this,e)}premultiply(e){return this.multiplyQuaternions(e,this)}multiplyQuaternions(e,t){const n=e._x,r=e._y,s=e._z,a=e._w,o=t._x,l=t._y,c=t._z,h=t._w;return this._x=n*h+a*o+r*c-s*l,this._y=r*h+a*l+s*o-n*c,this._z=s*h+a*c+n*l-r*o,this._w=a*h-n*o-r*l-s*c,this._onChangeCallback(),this}slerp(e,t){if(t===0)return this;if(t===1)return this.copy(e);const n=this._x,r=this._y,s=this._z,a=this._w;let o=a*e._w+n*e._x+r*e._y+s*e._z;if(o<0?(this._w=-e._w,this._x=-e._x,this._y=-e._y,this._z=-e._z,o=-o):this.copy(e),o>=1)return this._w=a,this._x=n,this._y=r,this._z=s,this;const l=1-o*o;if(l<=Number.EPSILON){const p=1-t;return this._w=p*a+t*this._w,this._x=p*n+t*this._x,this._y=p*r+t*this._y,this._z=p*s+t*this._z,this.normalize(),this}const c=Math.sqrt(l),h=Math.atan2(c,o),u=Math.sin((1-t)*h)/c,f=Math.sin(t*h)/c;return this._w=a*u+this._w*f,this._x=n*u+this._x*f,this._y=r*u+this._y*f,this._z=s*u+this._z*f,this._onChangeCallback(),this}slerpQuaternions(e,t,n){return this.copy(e).slerp(t,n)}random(){const e=2*Math.PI*Math.random(),t=2*Math.PI*Math.random(),n=Math.random(),r=Math.sqrt(1-n),s=Math.sqrt(n);return this.set(r*Math.sin(e),r*Math.cos(e),s*Math.sin(t),s*Math.cos(t))}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._w===this._w}fromArray(e,t=0){return this._x=e[t],this._y=e[t+1],this._z=e[t+2],this._w=e[t+3],this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._w,e}fromBufferAttribute(e,t){return this._x=e.getX(t),this._y=e.getY(t),this._z=e.getZ(t),this._w=e.getW(t),this._onChangeCallback(),this}toJSON(){return this.toArray()}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._w}}class P{constructor(e=0,t=0,n=0){P.prototype.isVector3=!0,this.x=e,this.y=t,this.z=n}set(e,t,n){return n===void 0&&(n=this.z),this.x=e,this.y=t,this.z=n,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y,this.z)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this}multiplyVectors(e,t){return this.x=e.x*t.x,this.y=e.y*t.y,this.z=e.z*t.z,this}applyEuler(e){return this.applyQuaternion($c.setFromEuler(e))}applyAxisAngle(e,t){return this.applyQuaternion($c.setFromAxisAngle(e,t))}applyMatrix3(e){const t=this.x,n=this.y,r=this.z,s=e.elements;return this.x=s[0]*t+s[3]*n+s[6]*r,this.y=s[1]*t+s[4]*n+s[7]*r,this.z=s[2]*t+s[5]*n+s[8]*r,this}applyNormalMatrix(e){return this.applyMatrix3(e).normalize()}applyMatrix4(e){const t=this.x,n=this.y,r=this.z,s=e.elements,a=1/(s[3]*t+s[7]*n+s[11]*r+s[15]);return this.x=(s[0]*t+s[4]*n+s[8]*r+s[12])*a,this.y=(s[1]*t+s[5]*n+s[9]*r+s[13])*a,this.z=(s[2]*t+s[6]*n+s[10]*r+s[14])*a,this}applyQuaternion(e){const t=this.x,n=this.y,r=this.z,s=e.x,a=e.y,o=e.z,l=e.w,c=2*(a*r-o*n),h=2*(o*t-s*r),u=2*(s*n-a*t);return this.x=t+l*c+a*u-o*h,this.y=n+l*h+o*c-s*u,this.z=r+l*u+s*h-a*c,this}project(e){return this.applyMatrix4(e.matrixWorldInverse).applyMatrix4(e.projectionMatrix)}unproject(e){return this.applyMatrix4(e.projectionMatrixInverse).applyMatrix4(e.matrixWorld)}transformDirection(e){const t=this.x,n=this.y,r=this.z,s=e.elements;return this.x=s[0]*t+s[4]*n+s[8]*r,this.y=s[1]*t+s[5]*n+s[9]*r,this.z=s[2]*t+s[6]*n+s[10]*r,this.normalize()}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this}divideScalar(e){return this.multiplyScalar(1/e)}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this}clamp(e,t){return this.x=Xe(this.x,e.x,t.x),this.y=Xe(this.y,e.y,t.y),this.z=Xe(this.z,e.z,t.z),this}clampScalar(e,t){return this.x=Xe(this.x,e,t),this.y=Xe(this.y,e,t),this.z=Xe(this.z,e,t),this}clampLength(e,t){const n=this.length();return this.divideScalar(n||1).multiplyScalar(Xe(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this}cross(e){return this.crossVectors(this,e)}crossVectors(e,t){const n=e.x,r=e.y,s=e.z,a=t.x,o=t.y,l=t.z;return this.x=r*l-s*o,this.y=s*a-n*l,this.z=n*o-r*a,this}projectOnVector(e){const t=e.lengthSq();if(t===0)return this.set(0,0,0);const n=e.dot(this)/t;return this.copy(e).multiplyScalar(n)}projectOnPlane(e){return io.copy(this).projectOnVector(e),this.sub(io)}reflect(e){return this.sub(io.copy(e).multiplyScalar(2*this.dot(e)))}angleTo(e){const t=Math.sqrt(this.lengthSq()*e.lengthSq());if(t===0)return Math.PI/2;const n=this.dot(e)/t;return Math.acos(Xe(n,-1,1))}distanceTo(e){return Math.sqrt(this.distanceToSquared(e))}distanceToSquared(e){const t=this.x-e.x,n=this.y-e.y,r=this.z-e.z;return t*t+n*n+r*r}manhattanDistanceTo(e){return Math.abs(this.x-e.x)+Math.abs(this.y-e.y)+Math.abs(this.z-e.z)}setFromSpherical(e){return this.setFromSphericalCoords(e.radius,e.phi,e.theta)}setFromSphericalCoords(e,t,n){const r=Math.sin(t)*e;return this.x=r*Math.sin(n),this.y=Math.cos(t)*e,this.z=r*Math.cos(n),this}setFromCylindrical(e){return this.setFromCylindricalCoords(e.radius,e.theta,e.y)}setFromCylindricalCoords(e,t,n){return this.x=e*Math.sin(t),this.y=n,this.z=e*Math.cos(t),this}setFromMatrixPosition(e){const t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this}setFromMatrixScale(e){const t=this.setFromMatrixColumn(e,0).length(),n=this.setFromMatrixColumn(e,1).length(),r=this.setFromMatrixColumn(e,2).length();return this.x=t,this.y=n,this.z=r,this}setFromMatrixColumn(e,t){return this.fromArray(e.elements,t*4)}setFromMatrix3Column(e,t){return this.fromArray(e.elements,t*3)}setFromEuler(e){return this.x=e._x,this.y=e._y,this.z=e._z,this}setFromColor(e){return this.x=e.r,this.y=e.g,this.z=e.b,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this}randomDirection(){const e=Math.random()*Math.PI*2,t=Math.random()*2-1,n=Math.sqrt(1-t*t);return this.x=n*Math.cos(e),this.y=t,this.z=n*Math.sin(e),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z}}const io=new P,$c=new En;class Ve{constructor(e,t,n,r,s,a,o,l,c){Ve.prototype.isMatrix3=!0,this.elements=[1,0,0,0,1,0,0,0,1],e!==void 0&&this.set(e,t,n,r,s,a,o,l,c)}set(e,t,n,r,s,a,o,l,c){const h=this.elements;return h[0]=e,h[1]=r,h[2]=o,h[3]=t,h[4]=s,h[5]=l,h[6]=n,h[7]=a,h[8]=c,this}identity(){return this.set(1,0,0,0,1,0,0,0,1),this}copy(e){const t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],this}extractBasis(e,t,n){return e.setFromMatrix3Column(this,0),t.setFromMatrix3Column(this,1),n.setFromMatrix3Column(this,2),this}setFromMatrix4(e){const t=e.elements;return this.set(t[0],t[4],t[8],t[1],t[5],t[9],t[2],t[6],t[10]),this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){const n=e.elements,r=t.elements,s=this.elements,a=n[0],o=n[3],l=n[6],c=n[1],h=n[4],u=n[7],f=n[2],p=n[5],_=n[8],y=r[0],g=r[3],m=r[6],E=r[1],w=r[4],x=r[7],T=r[2],L=r[5],C=r[8];return s[0]=a*y+o*E+l*T,s[3]=a*g+o*w+l*L,s[6]=a*m+o*x+l*C,s[1]=c*y+h*E+u*T,s[4]=c*g+h*w+u*L,s[7]=c*m+h*x+u*C,s[2]=f*y+p*E+_*T,s[5]=f*g+p*w+_*L,s[8]=f*m+p*x+_*C,this}multiplyScalar(e){const t=this.elements;return t[0]*=e,t[3]*=e,t[6]*=e,t[1]*=e,t[4]*=e,t[7]*=e,t[2]*=e,t[5]*=e,t[8]*=e,this}determinant(){const e=this.elements,t=e[0],n=e[1],r=e[2],s=e[3],a=e[4],o=e[5],l=e[6],c=e[7],h=e[8];return t*a*h-t*o*c-n*s*h+n*o*l+r*s*c-r*a*l}invert(){const e=this.elements,t=e[0],n=e[1],r=e[2],s=e[3],a=e[4],o=e[5],l=e[6],c=e[7],h=e[8],u=h*a-o*c,f=o*l-h*s,p=c*s-a*l,_=t*u+n*f+r*p;if(_===0)return this.set(0,0,0,0,0,0,0,0,0);const y=1/_;return e[0]=u*y,e[1]=(r*c-h*n)*y,e[2]=(o*n-r*a)*y,e[3]=f*y,e[4]=(h*t-r*l)*y,e[5]=(r*s-o*t)*y,e[6]=p*y,e[7]=(n*l-c*t)*y,e[8]=(a*t-n*s)*y,this}transpose(){let e;const t=this.elements;return e=t[1],t[1]=t[3],t[3]=e,e=t[2],t[2]=t[6],t[6]=e,e=t[5],t[5]=t[7],t[7]=e,this}getNormalMatrix(e){return this.setFromMatrix4(e).invert().transpose()}transposeIntoArray(e){const t=this.elements;return e[0]=t[0],e[1]=t[3],e[2]=t[6],e[3]=t[1],e[4]=t[4],e[5]=t[7],e[6]=t[2],e[7]=t[5],e[8]=t[8],this}setUvTransform(e,t,n,r,s,a,o){const l=Math.cos(s),c=Math.sin(s);return this.set(n*l,n*c,-n*(l*a+c*o)+a+e,-r*c,r*l,-r*(-c*a+l*o)+o+t,0,0,1),this}scale(e,t){return this.premultiply(ro.makeScale(e,t)),this}rotate(e){return this.premultiply(ro.makeRotation(-e)),this}translate(e,t){return this.premultiply(ro.makeTranslation(e,t)),this}makeTranslation(e,t){return e.isVector2?this.set(1,0,e.x,0,1,e.y,0,0,1):this.set(1,0,e,0,1,t,0,0,1),this}makeRotation(e){const t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,n,t,0,0,0,1),this}makeScale(e,t){return this.set(e,0,0,0,t,0,0,0,1),this}equals(e){const t=this.elements,n=e.elements;for(let r=0;r<9;r++)if(t[r]!==n[r])return!1;return!0}fromArray(e,t=0){for(let n=0;n<9;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){const n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e}clone(){return new this.constructor().fromArray(this.elements)}}const ro=new Ve;function zu(i){for(let e=i.length-1;e>=0;--e)if(i[e]>=65535)return!0;return!1}function ys(i){return document.createElementNS("http://www.w3.org/1999/xhtml",i)}function ap(){const i=ys("canvas");return i.style.display="block",i}const Zc={};function _r(i){i in Zc||(Zc[i]=!0,console.warn(i))}function op(i,e,t){return new Promise(function(n,r){function s(){switch(i.clientWaitSync(e,i.SYNC_FLUSH_COMMANDS_BIT,0)){case i.WAIT_FAILED:r();break;case i.TIMEOUT_EXPIRED:setTimeout(s,t);break;default:n()}}setTimeout(s,t)})}const Jc=new Ve().set(.4123908,.3575843,.1804808,.212639,.7151687,.0721923,.0193308,.1191948,.9505322),Qc=new Ve().set(3.2409699,-1.5373832,-.4986108,-.9692436,1.8759675,.0415551,.0556301,-.203977,1.0569715);function lp(){const i={enabled:!0,workingColorSpace:zt,spaces:{},convert:function(r,s,a){return this.enabled===!1||s===a||!s||!a||(this.spaces[s].transfer===lt&&(r.r=Jn(r.r),r.g=Jn(r.g),r.b=Jn(r.b)),this.spaces[s].primaries!==this.spaces[a].primaries&&(r.applyMatrix3(this.spaces[s].toXYZ),r.applyMatrix3(this.spaces[a].fromXYZ)),this.spaces[a].transfer===lt&&(r.r=yr(r.r),r.g=yr(r.g),r.b=yr(r.b))),r},workingToColorSpace:function(r,s){return this.convert(r,this.workingColorSpace,s)},colorSpaceToWorking:function(r,s){return this.convert(r,s,this.workingColorSpace)},getPrimaries:function(r){return this.spaces[r].primaries},getTransfer:function(r){return r===hi?Na:this.spaces[r].transfer},getLuminanceCoefficients:function(r,s=this.workingColorSpace){return r.fromArray(this.spaces[s].luminanceCoefficients)},define:function(r){Object.assign(this.spaces,r)},_getMatrix:function(r,s,a){return r.copy(this.spaces[s].toXYZ).multiply(this.spaces[a].fromXYZ)},_getDrawingBufferColorSpace:function(r){return this.spaces[r].outputColorSpaceConfig.drawingBufferColorSpace},_getUnpackColorSpace:function(r=this.workingColorSpace){return this.spaces[r].workingColorSpaceConfig.unpackColorSpace},fromWorkingColorSpace:function(r,s){return _r("THREE.ColorManagement: .fromWorkingColorSpace() has been renamed to .workingToColorSpace()."),i.workingToColorSpace(r,s)},toWorkingColorSpace:function(r,s){return _r("THREE.ColorManagement: .toWorkingColorSpace() has been renamed to .colorSpaceToWorking()."),i.colorSpaceToWorking(r,s)}},e=[.64,.33,.3,.6,.15,.06],t=[.2126,.7152,.0722],n=[.3127,.329];return i.define({[zt]:{primaries:e,whitePoint:n,transfer:Na,toXYZ:Jc,fromXYZ:Qc,luminanceCoefficients:t,workingColorSpaceConfig:{unpackColorSpace:Et},outputColorSpaceConfig:{drawingBufferColorSpace:Et}},[Et]:{primaries:e,whitePoint:n,transfer:lt,toXYZ:Jc,fromXYZ:Qc,luminanceCoefficients:t,outputColorSpaceConfig:{drawingBufferColorSpace:Et}}}),i}const Je=lp();function Jn(i){return i<.04045?i*.0773993808:Math.pow(i*.9478672986+.0521327014,2.4)}function yr(i){return i<.0031308?i*12.92:1.055*Math.pow(i,.41666)-.055}let Gi;class cp{static getDataURL(e,t="image/png"){if(/^data:/i.test(e.src)||typeof HTMLCanvasElement>"u")return e.src;let n;if(e instanceof HTMLCanvasElement)n=e;else{Gi===void 0&&(Gi=ys("canvas")),Gi.width=e.width,Gi.height=e.height;const r=Gi.getContext("2d");e instanceof ImageData?r.putImageData(e,0,0):r.drawImage(e,0,0,e.width,e.height),n=Gi}return n.toDataURL(t)}static sRGBToLinear(e){if(typeof HTMLImageElement<"u"&&e instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&e instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&e instanceof ImageBitmap){const t=ys("canvas");t.width=e.width,t.height=e.height;const n=t.getContext("2d");n.drawImage(e,0,0,e.width,e.height);const r=n.getImageData(0,0,e.width,e.height),s=r.data;for(let a=0;a<s.length;a++)s[a]=Jn(s[a]/255)*255;return n.putImageData(r,0,0),t}else if(e.data){const t=e.data.slice(0);for(let n=0;n<t.length;n++)t instanceof Uint8Array||t instanceof Uint8ClampedArray?t[n]=Math.floor(Jn(t[n]/255)*255):t[n]=Jn(t[n]);return{data:t,width:e.width,height:e.height}}else return console.warn("THREE.ImageUtils.sRGBToLinear(): Unsupported image type. No color space conversion applied."),e}}let dp=0;class tc{constructor(e=null){this.isSource=!0,Object.defineProperty(this,"id",{value:dp++}),this.uuid=bn(),this.data=e,this.dataReady=!0,this.version=0}getSize(e){const t=this.data;return t instanceof HTMLVideoElement?e.set(t.videoWidth,t.videoHeight,0):t instanceof VideoFrame?e.set(t.displayHeight,t.displayWidth,0):t!==null?e.set(t.width,t.height,t.depth||0):e.set(0,0,0),e}set needsUpdate(e){e===!0&&this.version++}toJSON(e){const t=e===void 0||typeof e=="string";if(!t&&e.images[this.uuid]!==void 0)return e.images[this.uuid];const n={uuid:this.uuid,url:""},r=this.data;if(r!==null){let s;if(Array.isArray(r)){s=[];for(let a=0,o=r.length;a<o;a++)r[a].isDataTexture?s.push(so(r[a].image)):s.push(so(r[a]))}else s=so(r);n.url=s}return t||(e.images[this.uuid]=n),n}}function so(i){return typeof HTMLImageElement<"u"&&i instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&i instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&i instanceof ImageBitmap?cp.getDataURL(i):i.data?{data:Array.from(i.data),width:i.width,height:i.height,type:i.data.constructor.name}:(console.warn("THREE.Texture: Unable to serialize Texture."),{})}let up=0;const ao=new P;class Ct extends Oi{constructor(e=Ct.DEFAULT_IMAGE,t=Ct.DEFAULT_MAPPING,n=Cn,r=Cn,s=Tt,a=Pn,o=sn,l=Sn,c=Ct.DEFAULT_ANISOTROPY,h=hi){super(),this.isTexture=!0,Object.defineProperty(this,"id",{value:up++}),this.uuid=bn(),this.name="",this.source=new tc(e),this.mipmaps=[],this.mapping=t,this.channel=0,this.wrapS=n,this.wrapT=r,this.magFilter=s,this.minFilter=a,this.anisotropy=c,this.format=o,this.internalFormat=null,this.type=l,this.offset=new xe(0,0),this.repeat=new xe(1,1),this.center=new xe(0,0),this.rotation=0,this.matrixAutoUpdate=!0,this.matrix=new Ve,this.generateMipmaps=!0,this.premultiplyAlpha=!1,this.flipY=!0,this.unpackAlignment=4,this.colorSpace=h,this.userData={},this.updateRanges=[],this.version=0,this.onUpdate=null,this.renderTarget=null,this.isRenderTargetTexture=!1,this.isArrayTexture=!!(e&&e.depth&&e.depth>1),this.pmremVersion=0}get width(){return this.source.getSize(ao).x}get height(){return this.source.getSize(ao).y}get depth(){return this.source.getSize(ao).z}get image(){return this.source.data}set image(e=null){this.source.data=e}updateMatrix(){this.matrix.setUvTransform(this.offset.x,this.offset.y,this.repeat.x,this.repeat.y,this.rotation,this.center.x,this.center.y)}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}clone(){return new this.constructor().copy(this)}copy(e){return this.name=e.name,this.source=e.source,this.mipmaps=e.mipmaps.slice(0),this.mapping=e.mapping,this.channel=e.channel,this.wrapS=e.wrapS,this.wrapT=e.wrapT,this.magFilter=e.magFilter,this.minFilter=e.minFilter,this.anisotropy=e.anisotropy,this.format=e.format,this.internalFormat=e.internalFormat,this.type=e.type,this.offset.copy(e.offset),this.repeat.copy(e.repeat),this.center.copy(e.center),this.rotation=e.rotation,this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrix.copy(e.matrix),this.generateMipmaps=e.generateMipmaps,this.premultiplyAlpha=e.premultiplyAlpha,this.flipY=e.flipY,this.unpackAlignment=e.unpackAlignment,this.colorSpace=e.colorSpace,this.renderTarget=e.renderTarget,this.isRenderTargetTexture=e.isRenderTargetTexture,this.isArrayTexture=e.isArrayTexture,this.userData=JSON.parse(JSON.stringify(e.userData)),this.needsUpdate=!0,this}setValues(e){for(const t in e){const n=e[t];if(n===void 0){console.warn(`THREE.Texture.setValues(): parameter '${t}' has value of undefined.`);continue}const r=this[t];if(r===void 0){console.warn(`THREE.Texture.setValues(): property '${t}' does not exist.`);continue}r&&n&&r.isVector2&&n.isVector2||r&&n&&r.isVector3&&n.isVector3||r&&n&&r.isMatrix3&&n.isMatrix3?r.copy(n):this[t]=n}}toJSON(e){const t=e===void 0||typeof e=="string";if(!t&&e.textures[this.uuid]!==void 0)return e.textures[this.uuid];const n={metadata:{version:4.7,type:"Texture",generator:"Texture.toJSON"},uuid:this.uuid,name:this.name,image:this.source.toJSON(e).uuid,mapping:this.mapping,channel:this.channel,repeat:[this.repeat.x,this.repeat.y],offset:[this.offset.x,this.offset.y],center:[this.center.x,this.center.y],rotation:this.rotation,wrap:[this.wrapS,this.wrapT],format:this.format,internalFormat:this.internalFormat,type:this.type,colorSpace:this.colorSpace,minFilter:this.minFilter,magFilter:this.magFilter,anisotropy:this.anisotropy,flipY:this.flipY,generateMipmaps:this.generateMipmaps,premultiplyAlpha:this.premultiplyAlpha,unpackAlignment:this.unpackAlignment};return Object.keys(this.userData).length>0&&(n.userData=this.userData),t||(e.textures[this.uuid]=n),n}dispose(){this.dispatchEvent({type:"dispose"})}transformUv(e){if(this.mapping!==Ru)return e;if(e.applyMatrix3(this.matrix),e.x<0||e.x>1)switch(this.wrapS){case _i:e.x=e.x-Math.floor(e.x);break;case Cn:e.x=e.x<0?0:1;break;case Da:Math.abs(Math.floor(e.x)%2)===1?e.x=Math.ceil(e.x)-e.x:e.x=e.x-Math.floor(e.x);break}if(e.y<0||e.y>1)switch(this.wrapT){case _i:e.y=e.y-Math.floor(e.y);break;case Cn:e.y=e.y<0?0:1;break;case Da:Math.abs(Math.floor(e.y)%2)===1?e.y=Math.ceil(e.y)-e.y:e.y=e.y-Math.floor(e.y);break}return this.flipY&&(e.y=1-e.y),e}set needsUpdate(e){e===!0&&(this.version++,this.source.needsUpdate=!0)}set needsPMREMUpdate(e){e===!0&&this.pmremVersion++}}Ct.DEFAULT_IMAGE=null;Ct.DEFAULT_MAPPING=Ru;Ct.DEFAULT_ANISOTROPY=1;class Ye{constructor(e=0,t=0,n=0,r=1){Ye.prototype.isVector4=!0,this.x=e,this.y=t,this.z=n,this.w=r}get width(){return this.z}set width(e){this.z=e}get height(){return this.w}set height(e){this.w=e}set(e,t,n,r){return this.x=e,this.y=t,this.z=n,this.w=r,this}setScalar(e){return this.x=e,this.y=e,this.z=e,this.w=e,this}setX(e){return this.x=e,this}setY(e){return this.y=e,this}setZ(e){return this.z=e,this}setW(e){return this.w=e,this}setComponent(e,t){switch(e){case 0:this.x=t;break;case 1:this.y=t;break;case 2:this.z=t;break;case 3:this.w=t;break;default:throw new Error("index is out of range: "+e)}return this}getComponent(e){switch(e){case 0:return this.x;case 1:return this.y;case 2:return this.z;case 3:return this.w;default:throw new Error("index is out of range: "+e)}}clone(){return new this.constructor(this.x,this.y,this.z,this.w)}copy(e){return this.x=e.x,this.y=e.y,this.z=e.z,this.w=e.w!==void 0?e.w:1,this}add(e){return this.x+=e.x,this.y+=e.y,this.z+=e.z,this.w+=e.w,this}addScalar(e){return this.x+=e,this.y+=e,this.z+=e,this.w+=e,this}addVectors(e,t){return this.x=e.x+t.x,this.y=e.y+t.y,this.z=e.z+t.z,this.w=e.w+t.w,this}addScaledVector(e,t){return this.x+=e.x*t,this.y+=e.y*t,this.z+=e.z*t,this.w+=e.w*t,this}sub(e){return this.x-=e.x,this.y-=e.y,this.z-=e.z,this.w-=e.w,this}subScalar(e){return this.x-=e,this.y-=e,this.z-=e,this.w-=e,this}subVectors(e,t){return this.x=e.x-t.x,this.y=e.y-t.y,this.z=e.z-t.z,this.w=e.w-t.w,this}multiply(e){return this.x*=e.x,this.y*=e.y,this.z*=e.z,this.w*=e.w,this}multiplyScalar(e){return this.x*=e,this.y*=e,this.z*=e,this.w*=e,this}applyMatrix4(e){const t=this.x,n=this.y,r=this.z,s=this.w,a=e.elements;return this.x=a[0]*t+a[4]*n+a[8]*r+a[12]*s,this.y=a[1]*t+a[5]*n+a[9]*r+a[13]*s,this.z=a[2]*t+a[6]*n+a[10]*r+a[14]*s,this.w=a[3]*t+a[7]*n+a[11]*r+a[15]*s,this}divide(e){return this.x/=e.x,this.y/=e.y,this.z/=e.z,this.w/=e.w,this}divideScalar(e){return this.multiplyScalar(1/e)}setAxisAngleFromQuaternion(e){this.w=2*Math.acos(e.w);const t=Math.sqrt(1-e.w*e.w);return t<1e-4?(this.x=1,this.y=0,this.z=0):(this.x=e.x/t,this.y=e.y/t,this.z=e.z/t),this}setAxisAngleFromRotationMatrix(e){let t,n,r,s;const l=e.elements,c=l[0],h=l[4],u=l[8],f=l[1],p=l[5],_=l[9],y=l[2],g=l[6],m=l[10];if(Math.abs(h-f)<.01&&Math.abs(u-y)<.01&&Math.abs(_-g)<.01){if(Math.abs(h+f)<.1&&Math.abs(u+y)<.1&&Math.abs(_+g)<.1&&Math.abs(c+p+m-3)<.1)return this.set(1,0,0,0),this;t=Math.PI;const w=(c+1)/2,x=(p+1)/2,T=(m+1)/2,L=(h+f)/4,C=(u+y)/4,R=(_+g)/4;return w>x&&w>T?w<.01?(n=0,r=.707106781,s=.707106781):(n=Math.sqrt(w),r=L/n,s=C/n):x>T?x<.01?(n=.707106781,r=0,s=.707106781):(r=Math.sqrt(x),n=L/r,s=R/r):T<.01?(n=.707106781,r=.707106781,s=0):(s=Math.sqrt(T),n=C/s,r=R/s),this.set(n,r,s,t),this}let E=Math.sqrt((g-_)*(g-_)+(u-y)*(u-y)+(f-h)*(f-h));return Math.abs(E)<.001&&(E=1),this.x=(g-_)/E,this.y=(u-y)/E,this.z=(f-h)/E,this.w=Math.acos((c+p+m-1)/2),this}setFromMatrixPosition(e){const t=e.elements;return this.x=t[12],this.y=t[13],this.z=t[14],this.w=t[15],this}min(e){return this.x=Math.min(this.x,e.x),this.y=Math.min(this.y,e.y),this.z=Math.min(this.z,e.z),this.w=Math.min(this.w,e.w),this}max(e){return this.x=Math.max(this.x,e.x),this.y=Math.max(this.y,e.y),this.z=Math.max(this.z,e.z),this.w=Math.max(this.w,e.w),this}clamp(e,t){return this.x=Xe(this.x,e.x,t.x),this.y=Xe(this.y,e.y,t.y),this.z=Xe(this.z,e.z,t.z),this.w=Xe(this.w,e.w,t.w),this}clampScalar(e,t){return this.x=Xe(this.x,e,t),this.y=Xe(this.y,e,t),this.z=Xe(this.z,e,t),this.w=Xe(this.w,e,t),this}clampLength(e,t){const n=this.length();return this.divideScalar(n||1).multiplyScalar(Xe(n,e,t))}floor(){return this.x=Math.floor(this.x),this.y=Math.floor(this.y),this.z=Math.floor(this.z),this.w=Math.floor(this.w),this}ceil(){return this.x=Math.ceil(this.x),this.y=Math.ceil(this.y),this.z=Math.ceil(this.z),this.w=Math.ceil(this.w),this}round(){return this.x=Math.round(this.x),this.y=Math.round(this.y),this.z=Math.round(this.z),this.w=Math.round(this.w),this}roundToZero(){return this.x=Math.trunc(this.x),this.y=Math.trunc(this.y),this.z=Math.trunc(this.z),this.w=Math.trunc(this.w),this}negate(){return this.x=-this.x,this.y=-this.y,this.z=-this.z,this.w=-this.w,this}dot(e){return this.x*e.x+this.y*e.y+this.z*e.z+this.w*e.w}lengthSq(){return this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w}length(){return Math.sqrt(this.x*this.x+this.y*this.y+this.z*this.z+this.w*this.w)}manhattanLength(){return Math.abs(this.x)+Math.abs(this.y)+Math.abs(this.z)+Math.abs(this.w)}normalize(){return this.divideScalar(this.length()||1)}setLength(e){return this.normalize().multiplyScalar(e)}lerp(e,t){return this.x+=(e.x-this.x)*t,this.y+=(e.y-this.y)*t,this.z+=(e.z-this.z)*t,this.w+=(e.w-this.w)*t,this}lerpVectors(e,t,n){return this.x=e.x+(t.x-e.x)*n,this.y=e.y+(t.y-e.y)*n,this.z=e.z+(t.z-e.z)*n,this.w=e.w+(t.w-e.w)*n,this}equals(e){return e.x===this.x&&e.y===this.y&&e.z===this.z&&e.w===this.w}fromArray(e,t=0){return this.x=e[t],this.y=e[t+1],this.z=e[t+2],this.w=e[t+3],this}toArray(e=[],t=0){return e[t]=this.x,e[t+1]=this.y,e[t+2]=this.z,e[t+3]=this.w,e}fromBufferAttribute(e,t){return this.x=e.getX(t),this.y=e.getY(t),this.z=e.getZ(t),this.w=e.getW(t),this}random(){return this.x=Math.random(),this.y=Math.random(),this.z=Math.random(),this.w=Math.random(),this}*[Symbol.iterator](){yield this.x,yield this.y,yield this.z,yield this.w}}class hp extends Oi{constructor(e=1,t=1,n={}){super(),n=Object.assign({generateMipmaps:!1,internalFormat:null,minFilter:Tt,depthBuffer:!0,stencilBuffer:!1,resolveDepthBuffer:!0,resolveStencilBuffer:!0,depthTexture:null,samples:0,count:1,depth:1,multiview:!1},n),this.isRenderTarget=!0,this.width=e,this.height=t,this.depth=n.depth,this.scissor=new Ye(0,0,e,t),this.scissorTest=!1,this.viewport=new Ye(0,0,e,t);const r={width:e,height:t,depth:n.depth},s=new Ct(r);this.textures=[];const a=n.count;for(let o=0;o<a;o++)this.textures[o]=s.clone(),this.textures[o].isRenderTargetTexture=!0,this.textures[o].renderTarget=this;this._setTextureOptions(n),this.depthBuffer=n.depthBuffer,this.stencilBuffer=n.stencilBuffer,this.resolveDepthBuffer=n.resolveDepthBuffer,this.resolveStencilBuffer=n.resolveStencilBuffer,this._depthTexture=null,this.depthTexture=n.depthTexture,this.samples=n.samples,this.multiview=n.multiview}_setTextureOptions(e={}){const t={minFilter:Tt,generateMipmaps:!1,flipY:!1,internalFormat:null};e.mapping!==void 0&&(t.mapping=e.mapping),e.wrapS!==void 0&&(t.wrapS=e.wrapS),e.wrapT!==void 0&&(t.wrapT=e.wrapT),e.wrapR!==void 0&&(t.wrapR=e.wrapR),e.magFilter!==void 0&&(t.magFilter=e.magFilter),e.minFilter!==void 0&&(t.minFilter=e.minFilter),e.format!==void 0&&(t.format=e.format),e.type!==void 0&&(t.type=e.type),e.anisotropy!==void 0&&(t.anisotropy=e.anisotropy),e.colorSpace!==void 0&&(t.colorSpace=e.colorSpace),e.flipY!==void 0&&(t.flipY=e.flipY),e.generateMipmaps!==void 0&&(t.generateMipmaps=e.generateMipmaps),e.internalFormat!==void 0&&(t.internalFormat=e.internalFormat);for(let n=0;n<this.textures.length;n++)this.textures[n].setValues(t)}get texture(){return this.textures[0]}set texture(e){this.textures[0]=e}set depthTexture(e){this._depthTexture!==null&&(this._depthTexture.renderTarget=null),e!==null&&(e.renderTarget=this),this._depthTexture=e}get depthTexture(){return this._depthTexture}setSize(e,t,n=1){if(this.width!==e||this.height!==t||this.depth!==n){this.width=e,this.height=t,this.depth=n;for(let r=0,s=this.textures.length;r<s;r++)this.textures[r].image.width=e,this.textures[r].image.height=t,this.textures[r].image.depth=n,this.textures[r].isArrayTexture=this.textures[r].image.depth>1;this.dispose()}this.viewport.set(0,0,e,t),this.scissor.set(0,0,e,t)}clone(){return new this.constructor().copy(this)}copy(e){this.width=e.width,this.height=e.height,this.depth=e.depth,this.scissor.copy(e.scissor),this.scissorTest=e.scissorTest,this.viewport.copy(e.viewport),this.textures.length=0;for(let t=0,n=e.textures.length;t<n;t++){this.textures[t]=e.textures[t].clone(),this.textures[t].isRenderTargetTexture=!0,this.textures[t].renderTarget=this;const r=Object.assign({},e.textures[t].image);this.textures[t].source=new tc(r)}return this.depthBuffer=e.depthBuffer,this.stencilBuffer=e.stencilBuffer,this.resolveDepthBuffer=e.resolveDepthBuffer,this.resolveStencilBuffer=e.resolveStencilBuffer,e.depthTexture!==null&&(this.depthTexture=e.depthTexture.clone()),this.samples=e.samples,this}dispose(){this.dispatchEvent({type:"dispose"})}}class Ni extends hp{constructor(e=1,t=1,n={}){super(e,t,n),this.isWebGLRenderTarget=!0}}class ku extends Ct{constructor(e=null,t=1,n=1,r=1){super(null),this.isDataArrayTexture=!0,this.image={data:e,width:t,height:n,depth:r},this.magFilter=qt,this.minFilter=qt,this.wrapR=Cn,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1,this.layerUpdates=new Set}addLayerUpdate(e){this.layerUpdates.add(e)}clearLayerUpdates(){this.layerUpdates.clear()}}class fp extends Ct{constructor(e=null,t=1,n=1,r=1){super(null),this.isData3DTexture=!0,this.image={data:e,width:t,height:n,depth:r},this.magFilter=qt,this.minFilter=qt,this.wrapR=Cn,this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}}class kt{constructor(e=new P(1/0,1/0,1/0),t=new P(-1/0,-1/0,-1/0)){this.isBox3=!0,this.min=e,this.max=t}set(e,t){return this.min.copy(e),this.max.copy(t),this}setFromArray(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t+=3)this.expandByPoint(gn.fromArray(e,t));return this}setFromBufferAttribute(e){this.makeEmpty();for(let t=0,n=e.count;t<n;t++)this.expandByPoint(gn.fromBufferAttribute(e,t));return this}setFromPoints(e){this.makeEmpty();for(let t=0,n=e.length;t<n;t++)this.expandByPoint(e[t]);return this}setFromCenterAndSize(e,t){const n=gn.copy(t).multiplyScalar(.5);return this.min.copy(e).sub(n),this.max.copy(e).add(n),this}setFromObject(e,t=!1){return this.makeEmpty(),this.expandByObject(e,t)}clone(){return new this.constructor().copy(this)}copy(e){return this.min.copy(e.min),this.max.copy(e.max),this}makeEmpty(){return this.min.x=this.min.y=this.min.z=1/0,this.max.x=this.max.y=this.max.z=-1/0,this}isEmpty(){return this.max.x<this.min.x||this.max.y<this.min.y||this.max.z<this.min.z}getCenter(e){return this.isEmpty()?e.set(0,0,0):e.addVectors(this.min,this.max).multiplyScalar(.5)}getSize(e){return this.isEmpty()?e.set(0,0,0):e.subVectors(this.max,this.min)}expandByPoint(e){return this.min.min(e),this.max.max(e),this}expandByVector(e){return this.min.sub(e),this.max.add(e),this}expandByScalar(e){return this.min.addScalar(-e),this.max.addScalar(e),this}expandByObject(e,t=!1){e.updateWorldMatrix(!1,!1);const n=e.geometry;if(n!==void 0){const s=n.getAttribute("position");if(t===!0&&s!==void 0&&e.isInstancedMesh!==!0)for(let a=0,o=s.count;a<o;a++)e.isMesh===!0?e.getVertexPosition(a,gn):gn.fromBufferAttribute(s,a),gn.applyMatrix4(e.matrixWorld),this.expandByPoint(gn);else e.boundingBox!==void 0?(e.boundingBox===null&&e.computeBoundingBox(),Bs.copy(e.boundingBox)):(n.boundingBox===null&&n.computeBoundingBox(),Bs.copy(n.boundingBox)),Bs.applyMatrix4(e.matrixWorld),this.union(Bs)}const r=e.children;for(let s=0,a=r.length;s<a;s++)this.expandByObject(r[s],t);return this}containsPoint(e){return e.x>=this.min.x&&e.x<=this.max.x&&e.y>=this.min.y&&e.y<=this.max.y&&e.z>=this.min.z&&e.z<=this.max.z}containsBox(e){return this.min.x<=e.min.x&&e.max.x<=this.max.x&&this.min.y<=e.min.y&&e.max.y<=this.max.y&&this.min.z<=e.min.z&&e.max.z<=this.max.z}getParameter(e,t){return t.set((e.x-this.min.x)/(this.max.x-this.min.x),(e.y-this.min.y)/(this.max.y-this.min.y),(e.z-this.min.z)/(this.max.z-this.min.z))}intersectsBox(e){return e.max.x>=this.min.x&&e.min.x<=this.max.x&&e.max.y>=this.min.y&&e.min.y<=this.max.y&&e.max.z>=this.min.z&&e.min.z<=this.max.z}intersectsSphere(e){return this.clampPoint(e.center,gn),gn.distanceToSquared(e.center)<=e.radius*e.radius}intersectsPlane(e){let t,n;return e.normal.x>0?(t=e.normal.x*this.min.x,n=e.normal.x*this.max.x):(t=e.normal.x*this.max.x,n=e.normal.x*this.min.x),e.normal.y>0?(t+=e.normal.y*this.min.y,n+=e.normal.y*this.max.y):(t+=e.normal.y*this.max.y,n+=e.normal.y*this.min.y),e.normal.z>0?(t+=e.normal.z*this.min.z,n+=e.normal.z*this.max.z):(t+=e.normal.z*this.max.z,n+=e.normal.z*this.min.z),t<=-e.constant&&n>=-e.constant}intersectsTriangle(e){if(this.isEmpty())return!1;this.getCenter(Vr),zs.subVectors(this.max,Vr),Vi.subVectors(e.a,Vr),Wi.subVectors(e.b,Vr),Xi.subVectors(e.c,Vr),si.subVectors(Wi,Vi),ai.subVectors(Xi,Wi),Mi.subVectors(Vi,Xi);let t=[0,-si.z,si.y,0,-ai.z,ai.y,0,-Mi.z,Mi.y,si.z,0,-si.x,ai.z,0,-ai.x,Mi.z,0,-Mi.x,-si.y,si.x,0,-ai.y,ai.x,0,-Mi.y,Mi.x,0];return!oo(t,Vi,Wi,Xi,zs)||(t=[1,0,0,0,1,0,0,0,1],!oo(t,Vi,Wi,Xi,zs))?!1:(ks.crossVectors(si,ai),t=[ks.x,ks.y,ks.z],oo(t,Vi,Wi,Xi,zs))}clampPoint(e,t){return t.copy(e).clamp(this.min,this.max)}distanceToPoint(e){return this.clampPoint(e,gn).distanceTo(e)}getBoundingSphere(e){return this.isEmpty()?e.makeEmpty():(this.getCenter(e.center),e.radius=this.getSize(gn).length()*.5),e}intersect(e){return this.min.max(e.min),this.max.min(e.max),this.isEmpty()&&this.makeEmpty(),this}union(e){return this.min.min(e.min),this.max.max(e.max),this}applyMatrix4(e){return this.isEmpty()?this:(Bn[0].set(this.min.x,this.min.y,this.min.z).applyMatrix4(e),Bn[1].set(this.min.x,this.min.y,this.max.z).applyMatrix4(e),Bn[2].set(this.min.x,this.max.y,this.min.z).applyMatrix4(e),Bn[3].set(this.min.x,this.max.y,this.max.z).applyMatrix4(e),Bn[4].set(this.max.x,this.min.y,this.min.z).applyMatrix4(e),Bn[5].set(this.max.x,this.min.y,this.max.z).applyMatrix4(e),Bn[6].set(this.max.x,this.max.y,this.min.z).applyMatrix4(e),Bn[7].set(this.max.x,this.max.y,this.max.z).applyMatrix4(e),this.setFromPoints(Bn),this)}translate(e){return this.min.add(e),this.max.add(e),this}equals(e){return e.min.equals(this.min)&&e.max.equals(this.max)}toJSON(){return{min:this.min.toArray(),max:this.max.toArray()}}fromJSON(e){return this.min.fromArray(e.min),this.max.fromArray(e.max),this}}const Bn=[new P,new P,new P,new P,new P,new P,new P,new P],gn=new P,Bs=new kt,Vi=new P,Wi=new P,Xi=new P,si=new P,ai=new P,Mi=new P,Vr=new P,zs=new P,ks=new P,bi=new P;function oo(i,e,t,n,r){for(let s=0,a=i.length-3;s<=a;s+=3){bi.fromArray(i,s);const o=r.x*Math.abs(bi.x)+r.y*Math.abs(bi.y)+r.z*Math.abs(bi.z),l=e.dot(bi),c=t.dot(bi),h=n.dot(bi);if(Math.max(-Math.max(l,c,h),Math.min(l,c,h))>o)return!1}return!0}const pp=new kt,Wr=new P,lo=new P;class Un{constructor(e=new P,t=-1){this.isSphere=!0,this.center=e,this.radius=t}set(e,t){return this.center.copy(e),this.radius=t,this}setFromPoints(e,t){const n=this.center;t!==void 0?n.copy(t):pp.setFromPoints(e).getCenter(n);let r=0;for(let s=0,a=e.length;s<a;s++)r=Math.max(r,n.distanceToSquared(e[s]));return this.radius=Math.sqrt(r),this}copy(e){return this.center.copy(e.center),this.radius=e.radius,this}isEmpty(){return this.radius<0}makeEmpty(){return this.center.set(0,0,0),this.radius=-1,this}containsPoint(e){return e.distanceToSquared(this.center)<=this.radius*this.radius}distanceToPoint(e){return e.distanceTo(this.center)-this.radius}intersectsSphere(e){const t=this.radius+e.radius;return e.center.distanceToSquared(this.center)<=t*t}intersectsBox(e){return e.intersectsSphere(this)}intersectsPlane(e){return Math.abs(e.distanceToPoint(this.center))<=this.radius}clampPoint(e,t){const n=this.center.distanceToSquared(e);return t.copy(e),n>this.radius*this.radius&&(t.sub(this.center).normalize(),t.multiplyScalar(this.radius).add(this.center)),t}getBoundingBox(e){return this.isEmpty()?(e.makeEmpty(),e):(e.set(this.center,this.center),e.expandByScalar(this.radius),e)}applyMatrix4(e){return this.center.applyMatrix4(e),this.radius=this.radius*e.getMaxScaleOnAxis(),this}translate(e){return this.center.add(e),this}expandByPoint(e){if(this.isEmpty())return this.center.copy(e),this.radius=0,this;Wr.subVectors(e,this.center);const t=Wr.lengthSq();if(t>this.radius*this.radius){const n=Math.sqrt(t),r=(n-this.radius)*.5;this.center.addScaledVector(Wr,r/n),this.radius+=r}return this}union(e){return e.isEmpty()?this:this.isEmpty()?(this.copy(e),this):(this.center.equals(e.center)===!0?this.radius=Math.max(this.radius,e.radius):(lo.subVectors(e.center,this.center).setLength(e.radius),this.expandByPoint(Wr.copy(e.center).add(lo)),this.expandByPoint(Wr.copy(e.center).sub(lo))),this)}equals(e){return e.center.equals(this.center)&&e.radius===this.radius}clone(){return new this.constructor().copy(this)}toJSON(){return{radius:this.radius,center:this.center.toArray()}}fromJSON(e){return this.radius=e.radius,this.center.fromArray(e.center),this}}const zn=new P,co=new P,Hs=new P,oi=new P,uo=new P,Gs=new P,ho=new P;class Fr{constructor(e=new P,t=new P(0,0,-1)){this.origin=e,this.direction=t}set(e,t){return this.origin.copy(e),this.direction.copy(t),this}copy(e){return this.origin.copy(e.origin),this.direction.copy(e.direction),this}at(e,t){return t.copy(this.origin).addScaledVector(this.direction,e)}lookAt(e){return this.direction.copy(e).sub(this.origin).normalize(),this}recast(e){return this.origin.copy(this.at(e,zn)),this}closestPointToPoint(e,t){t.subVectors(e,this.origin);const n=t.dot(this.direction);return n<0?t.copy(this.origin):t.copy(this.origin).addScaledVector(this.direction,n)}distanceToPoint(e){return Math.sqrt(this.distanceSqToPoint(e))}distanceSqToPoint(e){const t=zn.subVectors(e,this.origin).dot(this.direction);return t<0?this.origin.distanceToSquared(e):(zn.copy(this.origin).addScaledVector(this.direction,t),zn.distanceToSquared(e))}distanceSqToSegment(e,t,n,r){co.copy(e).add(t).multiplyScalar(.5),Hs.copy(t).sub(e).normalize(),oi.copy(this.origin).sub(co);const s=e.distanceTo(t)*.5,a=-this.direction.dot(Hs),o=oi.dot(this.direction),l=-oi.dot(Hs),c=oi.lengthSq(),h=Math.abs(1-a*a);let u,f,p,_;if(h>0)if(u=a*l-o,f=a*o-l,_=s*h,u>=0)if(f>=-_)if(f<=_){const y=1/h;u*=y,f*=y,p=u*(u+a*f+2*o)+f*(a*u+f+2*l)+c}else f=s,u=Math.max(0,-(a*f+o)),p=-u*u+f*(f+2*l)+c;else f=-s,u=Math.max(0,-(a*f+o)),p=-u*u+f*(f+2*l)+c;else f<=-_?(u=Math.max(0,-(-a*s+o)),f=u>0?-s:Math.min(Math.max(-s,-l),s),p=-u*u+f*(f+2*l)+c):f<=_?(u=0,f=Math.min(Math.max(-s,-l),s),p=f*(f+2*l)+c):(u=Math.max(0,-(a*s+o)),f=u>0?s:Math.min(Math.max(-s,-l),s),p=-u*u+f*(f+2*l)+c);else f=a>0?-s:s,u=Math.max(0,-(a*f+o)),p=-u*u+f*(f+2*l)+c;return n&&n.copy(this.origin).addScaledVector(this.direction,u),r&&r.copy(co).addScaledVector(Hs,f),p}intersectSphere(e,t){zn.subVectors(e.center,this.origin);const n=zn.dot(this.direction),r=zn.dot(zn)-n*n,s=e.radius*e.radius;if(r>s)return null;const a=Math.sqrt(s-r),o=n-a,l=n+a;return l<0?null:o<0?this.at(l,t):this.at(o,t)}intersectsSphere(e){return e.radius<0?!1:this.distanceSqToPoint(e.center)<=e.radius*e.radius}distanceToPlane(e){const t=e.normal.dot(this.direction);if(t===0)return e.distanceToPoint(this.origin)===0?0:null;const n=-(this.origin.dot(e.normal)+e.constant)/t;return n>=0?n:null}intersectPlane(e,t){const n=this.distanceToPlane(e);return n===null?null:this.at(n,t)}intersectsPlane(e){const t=e.distanceToPoint(this.origin);return t===0||e.normal.dot(this.direction)*t<0}intersectBox(e,t){let n,r,s,a,o,l;const c=1/this.direction.x,h=1/this.direction.y,u=1/this.direction.z,f=this.origin;return c>=0?(n=(e.min.x-f.x)*c,r=(e.max.x-f.x)*c):(n=(e.max.x-f.x)*c,r=(e.min.x-f.x)*c),h>=0?(s=(e.min.y-f.y)*h,a=(e.max.y-f.y)*h):(s=(e.max.y-f.y)*h,a=(e.min.y-f.y)*h),n>a||s>r||((s>n||isNaN(n))&&(n=s),(a<r||isNaN(r))&&(r=a),u>=0?(o=(e.min.z-f.z)*u,l=(e.max.z-f.z)*u):(o=(e.max.z-f.z)*u,l=(e.min.z-f.z)*u),n>l||o>r)||((o>n||n!==n)&&(n=o),(l<r||r!==r)&&(r=l),r<0)?null:this.at(n>=0?n:r,t)}intersectsBox(e){return this.intersectBox(e,zn)!==null}intersectTriangle(e,t,n,r,s){uo.subVectors(t,e),Gs.subVectors(n,e),ho.crossVectors(uo,Gs);let a=this.direction.dot(ho),o;if(a>0){if(r)return null;o=1}else if(a<0)o=-1,a=-a;else return null;oi.subVectors(this.origin,e);const l=o*this.direction.dot(Gs.crossVectors(oi,Gs));if(l<0)return null;const c=o*this.direction.dot(uo.cross(oi));if(c<0||l+c>a)return null;const h=-o*oi.dot(ho);return h<0?null:this.at(h/a,s)}applyMatrix4(e){return this.origin.applyMatrix4(e),this.direction.transformDirection(e),this}equals(e){return e.origin.equals(this.origin)&&e.direction.equals(this.direction)}clone(){return new this.constructor().copy(this)}}class De{constructor(e,t,n,r,s,a,o,l,c,h,u,f,p,_,y,g){De.prototype.isMatrix4=!0,this.elements=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],e!==void 0&&this.set(e,t,n,r,s,a,o,l,c,h,u,f,p,_,y,g)}set(e,t,n,r,s,a,o,l,c,h,u,f,p,_,y,g){const m=this.elements;return m[0]=e,m[4]=t,m[8]=n,m[12]=r,m[1]=s,m[5]=a,m[9]=o,m[13]=l,m[2]=c,m[6]=h,m[10]=u,m[14]=f,m[3]=p,m[7]=_,m[11]=y,m[15]=g,this}identity(){return this.set(1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1),this}clone(){return new De().fromArray(this.elements)}copy(e){const t=this.elements,n=e.elements;return t[0]=n[0],t[1]=n[1],t[2]=n[2],t[3]=n[3],t[4]=n[4],t[5]=n[5],t[6]=n[6],t[7]=n[7],t[8]=n[8],t[9]=n[9],t[10]=n[10],t[11]=n[11],t[12]=n[12],t[13]=n[13],t[14]=n[14],t[15]=n[15],this}copyPosition(e){const t=this.elements,n=e.elements;return t[12]=n[12],t[13]=n[13],t[14]=n[14],this}setFromMatrix3(e){const t=e.elements;return this.set(t[0],t[3],t[6],0,t[1],t[4],t[7],0,t[2],t[5],t[8],0,0,0,0,1),this}extractBasis(e,t,n){return e.setFromMatrixColumn(this,0),t.setFromMatrixColumn(this,1),n.setFromMatrixColumn(this,2),this}makeBasis(e,t,n){return this.set(e.x,t.x,n.x,0,e.y,t.y,n.y,0,e.z,t.z,n.z,0,0,0,0,1),this}extractRotation(e){const t=this.elements,n=e.elements,r=1/ji.setFromMatrixColumn(e,0).length(),s=1/ji.setFromMatrixColumn(e,1).length(),a=1/ji.setFromMatrixColumn(e,2).length();return t[0]=n[0]*r,t[1]=n[1]*r,t[2]=n[2]*r,t[3]=0,t[4]=n[4]*s,t[5]=n[5]*s,t[6]=n[6]*s,t[7]=0,t[8]=n[8]*a,t[9]=n[9]*a,t[10]=n[10]*a,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromEuler(e){const t=this.elements,n=e.x,r=e.y,s=e.z,a=Math.cos(n),o=Math.sin(n),l=Math.cos(r),c=Math.sin(r),h=Math.cos(s),u=Math.sin(s);if(e.order==="XYZ"){const f=a*h,p=a*u,_=o*h,y=o*u;t[0]=l*h,t[4]=-l*u,t[8]=c,t[1]=p+_*c,t[5]=f-y*c,t[9]=-o*l,t[2]=y-f*c,t[6]=_+p*c,t[10]=a*l}else if(e.order==="YXZ"){const f=l*h,p=l*u,_=c*h,y=c*u;t[0]=f+y*o,t[4]=_*o-p,t[8]=a*c,t[1]=a*u,t[5]=a*h,t[9]=-o,t[2]=p*o-_,t[6]=y+f*o,t[10]=a*l}else if(e.order==="ZXY"){const f=l*h,p=l*u,_=c*h,y=c*u;t[0]=f-y*o,t[4]=-a*u,t[8]=_+p*o,t[1]=p+_*o,t[5]=a*h,t[9]=y-f*o,t[2]=-a*c,t[6]=o,t[10]=a*l}else if(e.order==="ZYX"){const f=a*h,p=a*u,_=o*h,y=o*u;t[0]=l*h,t[4]=_*c-p,t[8]=f*c+y,t[1]=l*u,t[5]=y*c+f,t[9]=p*c-_,t[2]=-c,t[6]=o*l,t[10]=a*l}else if(e.order==="YZX"){const f=a*l,p=a*c,_=o*l,y=o*c;t[0]=l*h,t[4]=y-f*u,t[8]=_*u+p,t[1]=u,t[5]=a*h,t[9]=-o*h,t[2]=-c*h,t[6]=p*u+_,t[10]=f-y*u}else if(e.order==="XZY"){const f=a*l,p=a*c,_=o*l,y=o*c;t[0]=l*h,t[4]=-u,t[8]=c*h,t[1]=f*u+y,t[5]=a*h,t[9]=p*u-_,t[2]=_*u-p,t[6]=o*h,t[10]=y*u+f}return t[3]=0,t[7]=0,t[11]=0,t[12]=0,t[13]=0,t[14]=0,t[15]=1,this}makeRotationFromQuaternion(e){return this.compose(mp,e,gp)}lookAt(e,t,n){const r=this.elements;return en.subVectors(e,t),en.lengthSq()===0&&(en.z=1),en.normalize(),li.crossVectors(n,en),li.lengthSq()===0&&(Math.abs(n.z)===1?en.x+=1e-4:en.z+=1e-4,en.normalize(),li.crossVectors(n,en)),li.normalize(),Vs.crossVectors(en,li),r[0]=li.x,r[4]=Vs.x,r[8]=en.x,r[1]=li.y,r[5]=Vs.y,r[9]=en.y,r[2]=li.z,r[6]=Vs.z,r[10]=en.z,this}multiply(e){return this.multiplyMatrices(this,e)}premultiply(e){return this.multiplyMatrices(e,this)}multiplyMatrices(e,t){const n=e.elements,r=t.elements,s=this.elements,a=n[0],o=n[4],l=n[8],c=n[12],h=n[1],u=n[5],f=n[9],p=n[13],_=n[2],y=n[6],g=n[10],m=n[14],E=n[3],w=n[7],x=n[11],T=n[15],L=r[0],C=r[4],R=r[8],v=r[12],b=r[1],A=r[5],U=r[9],z=r[13],B=r[2],V=r[6],G=r[10],J=r[14],j=r[3],re=r[7],le=r[11],Re=r[15];return s[0]=a*L+o*b+l*B+c*j,s[4]=a*C+o*A+l*V+c*re,s[8]=a*R+o*U+l*G+c*le,s[12]=a*v+o*z+l*J+c*Re,s[1]=h*L+u*b+f*B+p*j,s[5]=h*C+u*A+f*V+p*re,s[9]=h*R+u*U+f*G+p*le,s[13]=h*v+u*z+f*J+p*Re,s[2]=_*L+y*b+g*B+m*j,s[6]=_*C+y*A+g*V+m*re,s[10]=_*R+y*U+g*G+m*le,s[14]=_*v+y*z+g*J+m*Re,s[3]=E*L+w*b+x*B+T*j,s[7]=E*C+w*A+x*V+T*re,s[11]=E*R+w*U+x*G+T*le,s[15]=E*v+w*z+x*J+T*Re,this}multiplyScalar(e){const t=this.elements;return t[0]*=e,t[4]*=e,t[8]*=e,t[12]*=e,t[1]*=e,t[5]*=e,t[9]*=e,t[13]*=e,t[2]*=e,t[6]*=e,t[10]*=e,t[14]*=e,t[3]*=e,t[7]*=e,t[11]*=e,t[15]*=e,this}determinant(){const e=this.elements,t=e[0],n=e[4],r=e[8],s=e[12],a=e[1],o=e[5],l=e[9],c=e[13],h=e[2],u=e[6],f=e[10],p=e[14],_=e[3],y=e[7],g=e[11],m=e[15];return _*(+s*l*u-r*c*u-s*o*f+n*c*f+r*o*p-n*l*p)+y*(+t*l*p-t*c*f+s*a*f-r*a*p+r*c*h-s*l*h)+g*(+t*c*u-t*o*p-s*a*u+n*a*p+s*o*h-n*c*h)+m*(-r*o*h-t*l*u+t*o*f+r*a*u-n*a*f+n*l*h)}transpose(){const e=this.elements;let t;return t=e[1],e[1]=e[4],e[4]=t,t=e[2],e[2]=e[8],e[8]=t,t=e[6],e[6]=e[9],e[9]=t,t=e[3],e[3]=e[12],e[12]=t,t=e[7],e[7]=e[13],e[13]=t,t=e[11],e[11]=e[14],e[14]=t,this}setPosition(e,t,n){const r=this.elements;return e.isVector3?(r[12]=e.x,r[13]=e.y,r[14]=e.z):(r[12]=e,r[13]=t,r[14]=n),this}invert(){const e=this.elements,t=e[0],n=e[1],r=e[2],s=e[3],a=e[4],o=e[5],l=e[6],c=e[7],h=e[8],u=e[9],f=e[10],p=e[11],_=e[12],y=e[13],g=e[14],m=e[15],E=u*g*c-y*f*c+y*l*p-o*g*p-u*l*m+o*f*m,w=_*f*c-h*g*c-_*l*p+a*g*p+h*l*m-a*f*m,x=h*y*c-_*u*c+_*o*p-a*y*p-h*o*m+a*u*m,T=_*u*l-h*y*l-_*o*f+a*y*f+h*o*g-a*u*g,L=t*E+n*w+r*x+s*T;if(L===0)return this.set(0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0);const C=1/L;return e[0]=E*C,e[1]=(y*f*s-u*g*s-y*r*p+n*g*p+u*r*m-n*f*m)*C,e[2]=(o*g*s-y*l*s+y*r*c-n*g*c-o*r*m+n*l*m)*C,e[3]=(u*l*s-o*f*s-u*r*c+n*f*c+o*r*p-n*l*p)*C,e[4]=w*C,e[5]=(h*g*s-_*f*s+_*r*p-t*g*p-h*r*m+t*f*m)*C,e[6]=(_*l*s-a*g*s-_*r*c+t*g*c+a*r*m-t*l*m)*C,e[7]=(a*f*s-h*l*s+h*r*c-t*f*c-a*r*p+t*l*p)*C,e[8]=x*C,e[9]=(_*u*s-h*y*s-_*n*p+t*y*p+h*n*m-t*u*m)*C,e[10]=(a*y*s-_*o*s+_*n*c-t*y*c-a*n*m+t*o*m)*C,e[11]=(h*o*s-a*u*s-h*n*c+t*u*c+a*n*p-t*o*p)*C,e[12]=T*C,e[13]=(h*y*r-_*u*r+_*n*f-t*y*f-h*n*g+t*u*g)*C,e[14]=(_*o*r-a*y*r-_*n*l+t*y*l+a*n*g-t*o*g)*C,e[15]=(a*u*r-h*o*r+h*n*l-t*u*l-a*n*f+t*o*f)*C,this}scale(e){const t=this.elements,n=e.x,r=e.y,s=e.z;return t[0]*=n,t[4]*=r,t[8]*=s,t[1]*=n,t[5]*=r,t[9]*=s,t[2]*=n,t[6]*=r,t[10]*=s,t[3]*=n,t[7]*=r,t[11]*=s,this}getMaxScaleOnAxis(){const e=this.elements,t=e[0]*e[0]+e[1]*e[1]+e[2]*e[2],n=e[4]*e[4]+e[5]*e[5]+e[6]*e[6],r=e[8]*e[8]+e[9]*e[9]+e[10]*e[10];return Math.sqrt(Math.max(t,n,r))}makeTranslation(e,t,n){return e.isVector3?this.set(1,0,0,e.x,0,1,0,e.y,0,0,1,e.z,0,0,0,1):this.set(1,0,0,e,0,1,0,t,0,0,1,n,0,0,0,1),this}makeRotationX(e){const t=Math.cos(e),n=Math.sin(e);return this.set(1,0,0,0,0,t,-n,0,0,n,t,0,0,0,0,1),this}makeRotationY(e){const t=Math.cos(e),n=Math.sin(e);return this.set(t,0,n,0,0,1,0,0,-n,0,t,0,0,0,0,1),this}makeRotationZ(e){const t=Math.cos(e),n=Math.sin(e);return this.set(t,-n,0,0,n,t,0,0,0,0,1,0,0,0,0,1),this}makeRotationAxis(e,t){const n=Math.cos(t),r=Math.sin(t),s=1-n,a=e.x,o=e.y,l=e.z,c=s*a,h=s*o;return this.set(c*a+n,c*o-r*l,c*l+r*o,0,c*o+r*l,h*o+n,h*l-r*a,0,c*l-r*o,h*l+r*a,s*l*l+n,0,0,0,0,1),this}makeScale(e,t,n){return this.set(e,0,0,0,0,t,0,0,0,0,n,0,0,0,0,1),this}makeShear(e,t,n,r,s,a){return this.set(1,n,s,0,e,1,a,0,t,r,1,0,0,0,0,1),this}compose(e,t,n){const r=this.elements,s=t._x,a=t._y,o=t._z,l=t._w,c=s+s,h=a+a,u=o+o,f=s*c,p=s*h,_=s*u,y=a*h,g=a*u,m=o*u,E=l*c,w=l*h,x=l*u,T=n.x,L=n.y,C=n.z;return r[0]=(1-(y+m))*T,r[1]=(p+x)*T,r[2]=(_-w)*T,r[3]=0,r[4]=(p-x)*L,r[5]=(1-(f+m))*L,r[6]=(g+E)*L,r[7]=0,r[8]=(_+w)*C,r[9]=(g-E)*C,r[10]=(1-(f+y))*C,r[11]=0,r[12]=e.x,r[13]=e.y,r[14]=e.z,r[15]=1,this}decompose(e,t,n){const r=this.elements;let s=ji.set(r[0],r[1],r[2]).length();const a=ji.set(r[4],r[5],r[6]).length(),o=ji.set(r[8],r[9],r[10]).length();this.determinant()<0&&(s=-s),e.x=r[12],e.y=r[13],e.z=r[14],_n.copy(this);const c=1/s,h=1/a,u=1/o;return _n.elements[0]*=c,_n.elements[1]*=c,_n.elements[2]*=c,_n.elements[4]*=h,_n.elements[5]*=h,_n.elements[6]*=h,_n.elements[8]*=u,_n.elements[9]*=u,_n.elements[10]*=u,t.setFromRotationMatrix(_n),n.x=s,n.y=a,n.z=o,this}makePerspective(e,t,n,r,s,a,o=Ln,l=!1){const c=this.elements,h=2*s/(t-e),u=2*s/(n-r),f=(t+e)/(t-e),p=(n+r)/(n-r);let _,y;if(l)_=s/(a-s),y=a*s/(a-s);else if(o===Ln)_=-(a+s)/(a-s),y=-2*a*s/(a-s);else if(o===Ua)_=-a/(a-s),y=-a*s/(a-s);else throw new Error("THREE.Matrix4.makePerspective(): Invalid coordinate system: "+o);return c[0]=h,c[4]=0,c[8]=f,c[12]=0,c[1]=0,c[5]=u,c[9]=p,c[13]=0,c[2]=0,c[6]=0,c[10]=_,c[14]=y,c[3]=0,c[7]=0,c[11]=-1,c[15]=0,this}makeOrthographic(e,t,n,r,s,a,o=Ln,l=!1){const c=this.elements,h=2/(t-e),u=2/(n-r),f=-(t+e)/(t-e),p=-(n+r)/(n-r);let _,y;if(l)_=1/(a-s),y=a/(a-s);else if(o===Ln)_=-2/(a-s),y=-(a+s)/(a-s);else if(o===Ua)_=-1/(a-s),y=-s/(a-s);else throw new Error("THREE.Matrix4.makeOrthographic(): Invalid coordinate system: "+o);return c[0]=h,c[4]=0,c[8]=0,c[12]=f,c[1]=0,c[5]=u,c[9]=0,c[13]=p,c[2]=0,c[6]=0,c[10]=_,c[14]=y,c[3]=0,c[7]=0,c[11]=0,c[15]=1,this}equals(e){const t=this.elements,n=e.elements;for(let r=0;r<16;r++)if(t[r]!==n[r])return!1;return!0}fromArray(e,t=0){for(let n=0;n<16;n++)this.elements[n]=e[n+t];return this}toArray(e=[],t=0){const n=this.elements;return e[t]=n[0],e[t+1]=n[1],e[t+2]=n[2],e[t+3]=n[3],e[t+4]=n[4],e[t+5]=n[5],e[t+6]=n[6],e[t+7]=n[7],e[t+8]=n[8],e[t+9]=n[9],e[t+10]=n[10],e[t+11]=n[11],e[t+12]=n[12],e[t+13]=n[13],e[t+14]=n[14],e[t+15]=n[15],e}}const ji=new P,_n=new De,mp=new P(0,0,0),gp=new P(1,1,1),li=new P,Vs=new P,en=new P,ed=new De,td=new En;class pn{constructor(e=0,t=0,n=0,r=pn.DEFAULT_ORDER){this.isEuler=!0,this._x=e,this._y=t,this._z=n,this._order=r}get x(){return this._x}set x(e){this._x=e,this._onChangeCallback()}get y(){return this._y}set y(e){this._y=e,this._onChangeCallback()}get z(){return this._z}set z(e){this._z=e,this._onChangeCallback()}get order(){return this._order}set order(e){this._order=e,this._onChangeCallback()}set(e,t,n,r=this._order){return this._x=e,this._y=t,this._z=n,this._order=r,this._onChangeCallback(),this}clone(){return new this.constructor(this._x,this._y,this._z,this._order)}copy(e){return this._x=e._x,this._y=e._y,this._z=e._z,this._order=e._order,this._onChangeCallback(),this}setFromRotationMatrix(e,t=this._order,n=!0){const r=e.elements,s=r[0],a=r[4],o=r[8],l=r[1],c=r[5],h=r[9],u=r[2],f=r[6],p=r[10];switch(t){case"XYZ":this._y=Math.asin(Xe(o,-1,1)),Math.abs(o)<.9999999?(this._x=Math.atan2(-h,p),this._z=Math.atan2(-a,s)):(this._x=Math.atan2(f,c),this._z=0);break;case"YXZ":this._x=Math.asin(-Xe(h,-1,1)),Math.abs(h)<.9999999?(this._y=Math.atan2(o,p),this._z=Math.atan2(l,c)):(this._y=Math.atan2(-u,s),this._z=0);break;case"ZXY":this._x=Math.asin(Xe(f,-1,1)),Math.abs(f)<.9999999?(this._y=Math.atan2(-u,p),this._z=Math.atan2(-a,c)):(this._y=0,this._z=Math.atan2(l,s));break;case"ZYX":this._y=Math.asin(-Xe(u,-1,1)),Math.abs(u)<.9999999?(this._x=Math.atan2(f,p),this._z=Math.atan2(l,s)):(this._x=0,this._z=Math.atan2(-a,c));break;case"YZX":this._z=Math.asin(Xe(l,-1,1)),Math.abs(l)<.9999999?(this._x=Math.atan2(-h,c),this._y=Math.atan2(-u,s)):(this._x=0,this._y=Math.atan2(o,p));break;case"XZY":this._z=Math.asin(-Xe(a,-1,1)),Math.abs(a)<.9999999?(this._x=Math.atan2(f,c),this._y=Math.atan2(o,s)):(this._x=Math.atan2(-h,p),this._y=0);break;default:console.warn("THREE.Euler: .setFromRotationMatrix() encountered an unknown order: "+t)}return this._order=t,n===!0&&this._onChangeCallback(),this}setFromQuaternion(e,t,n){return ed.makeRotationFromQuaternion(e),this.setFromRotationMatrix(ed,t,n)}setFromVector3(e,t=this._order){return this.set(e.x,e.y,e.z,t)}reorder(e){return td.setFromEuler(this),this.setFromQuaternion(td,e)}equals(e){return e._x===this._x&&e._y===this._y&&e._z===this._z&&e._order===this._order}fromArray(e){return this._x=e[0],this._y=e[1],this._z=e[2],e[3]!==void 0&&(this._order=e[3]),this._onChangeCallback(),this}toArray(e=[],t=0){return e[t]=this._x,e[t+1]=this._y,e[t+2]=this._z,e[t+3]=this._order,e}_onChange(e){return this._onChangeCallback=e,this}_onChangeCallback(){}*[Symbol.iterator](){yield this._x,yield this._y,yield this._z,yield this._order}}pn.DEFAULT_ORDER="XYZ";class nc{constructor(){this.mask=1}set(e){this.mask=(1<<e|0)>>>0}enable(e){this.mask|=1<<e|0}enableAll(){this.mask=-1}toggle(e){this.mask^=1<<e|0}disable(e){this.mask&=~(1<<e|0)}disableAll(){this.mask=0}test(e){return(this.mask&e.mask)!==0}isEnabled(e){return(this.mask&(1<<e|0))!==0}}let _p=0;const nd=new P,qi=new En,kn=new De,Ws=new P,Xr=new P,yp=new P,xp=new En,id=new P(1,0,0),rd=new P(0,1,0),sd=new P(0,0,1),ad={type:"added"},vp={type:"removed"},Yi={type:"childadded",child:null},fo={type:"childremoved",child:null};class pt extends Oi{constructor(){super(),this.isObject3D=!0,Object.defineProperty(this,"id",{value:_p++}),this.uuid=bn(),this.name="",this.type="Object3D",this.parent=null,this.children=[],this.up=pt.DEFAULT_UP.clone();const e=new P,t=new pn,n=new En,r=new P(1,1,1);function s(){n.setFromEuler(t,!1)}function a(){t.setFromQuaternion(n,void 0,!1)}t._onChange(s),n._onChange(a),Object.defineProperties(this,{position:{configurable:!0,enumerable:!0,value:e},rotation:{configurable:!0,enumerable:!0,value:t},quaternion:{configurable:!0,enumerable:!0,value:n},scale:{configurable:!0,enumerable:!0,value:r},modelViewMatrix:{value:new De},normalMatrix:{value:new Ve}}),this.matrix=new De,this.matrixWorld=new De,this.matrixAutoUpdate=pt.DEFAULT_MATRIX_AUTO_UPDATE,this.matrixWorldAutoUpdate=pt.DEFAULT_MATRIX_WORLD_AUTO_UPDATE,this.matrixWorldNeedsUpdate=!1,this.layers=new nc,this.visible=!0,this.castShadow=!1,this.receiveShadow=!1,this.frustumCulled=!0,this.renderOrder=0,this.animations=[],this.customDepthMaterial=void 0,this.customDistanceMaterial=void 0,this.userData={}}onBeforeShadow(){}onAfterShadow(){}onBeforeRender(){}onAfterRender(){}applyMatrix4(e){this.matrixAutoUpdate&&this.updateMatrix(),this.matrix.premultiply(e),this.matrix.decompose(this.position,this.quaternion,this.scale)}applyQuaternion(e){return this.quaternion.premultiply(e),this}setRotationFromAxisAngle(e,t){this.quaternion.setFromAxisAngle(e,t)}setRotationFromEuler(e){this.quaternion.setFromEuler(e,!0)}setRotationFromMatrix(e){this.quaternion.setFromRotationMatrix(e)}setRotationFromQuaternion(e){this.quaternion.copy(e)}rotateOnAxis(e,t){return qi.setFromAxisAngle(e,t),this.quaternion.multiply(qi),this}rotateOnWorldAxis(e,t){return qi.setFromAxisAngle(e,t),this.quaternion.premultiply(qi),this}rotateX(e){return this.rotateOnAxis(id,e)}rotateY(e){return this.rotateOnAxis(rd,e)}rotateZ(e){return this.rotateOnAxis(sd,e)}translateOnAxis(e,t){return nd.copy(e).applyQuaternion(this.quaternion),this.position.add(nd.multiplyScalar(t)),this}translateX(e){return this.translateOnAxis(id,e)}translateY(e){return this.translateOnAxis(rd,e)}translateZ(e){return this.translateOnAxis(sd,e)}localToWorld(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(this.matrixWorld)}worldToLocal(e){return this.updateWorldMatrix(!0,!1),e.applyMatrix4(kn.copy(this.matrixWorld).invert())}lookAt(e,t,n){e.isVector3?Ws.copy(e):Ws.set(e,t,n);const r=this.parent;this.updateWorldMatrix(!0,!1),Xr.setFromMatrixPosition(this.matrixWorld),this.isCamera||this.isLight?kn.lookAt(Xr,Ws,this.up):kn.lookAt(Ws,Xr,this.up),this.quaternion.setFromRotationMatrix(kn),r&&(kn.extractRotation(r.matrixWorld),qi.setFromRotationMatrix(kn),this.quaternion.premultiply(qi.invert()))}add(e){if(arguments.length>1){for(let t=0;t<arguments.length;t++)this.add(arguments[t]);return this}return e===this?(console.error("THREE.Object3D.add: object can't be added as a child of itself.",e),this):(e&&e.isObject3D?(e.removeFromParent(),e.parent=this,this.children.push(e),e.dispatchEvent(ad),Yi.child=e,this.dispatchEvent(Yi),Yi.child=null):console.error("THREE.Object3D.add: object not an instance of THREE.Object3D.",e),this)}remove(e){if(arguments.length>1){for(let n=0;n<arguments.length;n++)this.remove(arguments[n]);return this}const t=this.children.indexOf(e);return t!==-1&&(e.parent=null,this.children.splice(t,1),e.dispatchEvent(vp),fo.child=e,this.dispatchEvent(fo),fo.child=null),this}removeFromParent(){const e=this.parent;return e!==null&&e.remove(this),this}clear(){return this.remove(...this.children)}attach(e){return this.updateWorldMatrix(!0,!1),kn.copy(this.matrixWorld).invert(),e.parent!==null&&(e.parent.updateWorldMatrix(!0,!1),kn.multiply(e.parent.matrixWorld)),e.applyMatrix4(kn),e.removeFromParent(),e.parent=this,this.children.push(e),e.updateWorldMatrix(!1,!0),e.dispatchEvent(ad),Yi.child=e,this.dispatchEvent(Yi),Yi.child=null,this}getObjectById(e){return this.getObjectByProperty("id",e)}getObjectByName(e){return this.getObjectByProperty("name",e)}getObjectByProperty(e,t){if(this[e]===t)return this;for(let n=0,r=this.children.length;n<r;n++){const a=this.children[n].getObjectByProperty(e,t);if(a!==void 0)return a}}getObjectsByProperty(e,t,n=[]){this[e]===t&&n.push(this);const r=this.children;for(let s=0,a=r.length;s<a;s++)r[s].getObjectsByProperty(e,t,n);return n}getWorldPosition(e){return this.updateWorldMatrix(!0,!1),e.setFromMatrixPosition(this.matrixWorld)}getWorldQuaternion(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(Xr,e,yp),e}getWorldScale(e){return this.updateWorldMatrix(!0,!1),this.matrixWorld.decompose(Xr,xp,e),e}getWorldDirection(e){this.updateWorldMatrix(!0,!1);const t=this.matrixWorld.elements;return e.set(t[8],t[9],t[10]).normalize()}raycast(){}traverse(e){e(this);const t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].traverse(e)}traverseVisible(e){if(this.visible===!1)return;e(this);const t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].traverseVisible(e)}traverseAncestors(e){const t=this.parent;t!==null&&(e(t),t.traverseAncestors(e))}updateMatrix(){this.matrix.compose(this.position,this.quaternion,this.scale),this.matrixWorldNeedsUpdate=!0}updateMatrixWorld(e){this.matrixAutoUpdate&&this.updateMatrix(),(this.matrixWorldNeedsUpdate||e)&&(this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),this.matrixWorldNeedsUpdate=!1,e=!0);const t=this.children;for(let n=0,r=t.length;n<r;n++)t[n].updateMatrixWorld(e)}updateWorldMatrix(e,t){const n=this.parent;if(e===!0&&n!==null&&n.updateWorldMatrix(!0,!1),this.matrixAutoUpdate&&this.updateMatrix(),this.matrixWorldAutoUpdate===!0&&(this.parent===null?this.matrixWorld.copy(this.matrix):this.matrixWorld.multiplyMatrices(this.parent.matrixWorld,this.matrix)),t===!0){const r=this.children;for(let s=0,a=r.length;s<a;s++)r[s].updateWorldMatrix(!1,!0)}}toJSON(e){const t=e===void 0||typeof e=="string",n={};t&&(e={geometries:{},materials:{},textures:{},images:{},shapes:{},skeletons:{},animations:{},nodes:{}},n.metadata={version:4.7,type:"Object",generator:"Object3D.toJSON"});const r={};r.uuid=this.uuid,r.type=this.type,this.name!==""&&(r.name=this.name),this.castShadow===!0&&(r.castShadow=!0),this.receiveShadow===!0&&(r.receiveShadow=!0),this.visible===!1&&(r.visible=!1),this.frustumCulled===!1&&(r.frustumCulled=!1),this.renderOrder!==0&&(r.renderOrder=this.renderOrder),Object.keys(this.userData).length>0&&(r.userData=this.userData),r.layers=this.layers.mask,r.matrix=this.matrix.toArray(),r.up=this.up.toArray(),this.matrixAutoUpdate===!1&&(r.matrixAutoUpdate=!1),this.isInstancedMesh&&(r.type="InstancedMesh",r.count=this.count,r.instanceMatrix=this.instanceMatrix.toJSON(),this.instanceColor!==null&&(r.instanceColor=this.instanceColor.toJSON())),this.isBatchedMesh&&(r.type="BatchedMesh",r.perObjectFrustumCulled=this.perObjectFrustumCulled,r.sortObjects=this.sortObjects,r.drawRanges=this._drawRanges,r.reservedRanges=this._reservedRanges,r.geometryInfo=this._geometryInfo.map(o=>({...o,boundingBox:o.boundingBox?o.boundingBox.toJSON():void 0,boundingSphere:o.boundingSphere?o.boundingSphere.toJSON():void 0})),r.instanceInfo=this._instanceInfo.map(o=>({...o})),r.availableInstanceIds=this._availableInstanceIds.slice(),r.availableGeometryIds=this._availableGeometryIds.slice(),r.nextIndexStart=this._nextIndexStart,r.nextVertexStart=this._nextVertexStart,r.geometryCount=this._geometryCount,r.maxInstanceCount=this._maxInstanceCount,r.maxVertexCount=this._maxVertexCount,r.maxIndexCount=this._maxIndexCount,r.geometryInitialized=this._geometryInitialized,r.matricesTexture=this._matricesTexture.toJSON(e),r.indirectTexture=this._indirectTexture.toJSON(e),this._colorsTexture!==null&&(r.colorsTexture=this._colorsTexture.toJSON(e)),this.boundingSphere!==null&&(r.boundingSphere=this.boundingSphere.toJSON()),this.boundingBox!==null&&(r.boundingBox=this.boundingBox.toJSON()));function s(o,l){return o[l.uuid]===void 0&&(o[l.uuid]=l.toJSON(e)),l.uuid}if(this.isScene)this.background&&(this.background.isColor?r.background=this.background.toJSON():this.background.isTexture&&(r.background=this.background.toJSON(e).uuid)),this.environment&&this.environment.isTexture&&this.environment.isRenderTargetTexture!==!0&&(r.environment=this.environment.toJSON(e).uuid);else if(this.isMesh||this.isLine||this.isPoints){r.geometry=s(e.geometries,this.geometry);const o=this.geometry.parameters;if(o!==void 0&&o.shapes!==void 0){const l=o.shapes;if(Array.isArray(l))for(let c=0,h=l.length;c<h;c++){const u=l[c];s(e.shapes,u)}else s(e.shapes,l)}}if(this.isSkinnedMesh&&(r.bindMode=this.bindMode,r.bindMatrix=this.bindMatrix.toArray(),this.skeleton!==void 0&&(s(e.skeletons,this.skeleton),r.skeleton=this.skeleton.uuid)),this.material!==void 0)if(Array.isArray(this.material)){const o=[];for(let l=0,c=this.material.length;l<c;l++)o.push(s(e.materials,this.material[l]));r.material=o}else r.material=s(e.materials,this.material);if(this.children.length>0){r.children=[];for(let o=0;o<this.children.length;o++)r.children.push(this.children[o].toJSON(e).object)}if(this.animations.length>0){r.animations=[];for(let o=0;o<this.animations.length;o++){const l=this.animations[o];r.animations.push(s(e.animations,l))}}if(t){const o=a(e.geometries),l=a(e.materials),c=a(e.textures),h=a(e.images),u=a(e.shapes),f=a(e.skeletons),p=a(e.animations),_=a(e.nodes);o.length>0&&(n.geometries=o),l.length>0&&(n.materials=l),c.length>0&&(n.textures=c),h.length>0&&(n.images=h),u.length>0&&(n.shapes=u),f.length>0&&(n.skeletons=f),p.length>0&&(n.animations=p),_.length>0&&(n.nodes=_)}return n.object=r,n;function a(o){const l=[];for(const c in o){const h=o[c];delete h.metadata,l.push(h)}return l}}clone(e){return new this.constructor().copy(this,e)}copy(e,t=!0){if(this.name=e.name,this.up.copy(e.up),this.position.copy(e.position),this.rotation.order=e.rotation.order,this.quaternion.copy(e.quaternion),this.scale.copy(e.scale),this.matrix.copy(e.matrix),this.matrixWorld.copy(e.matrixWorld),this.matrixAutoUpdate=e.matrixAutoUpdate,this.matrixWorldAutoUpdate=e.matrixWorldAutoUpdate,this.matrixWorldNeedsUpdate=e.matrixWorldNeedsUpdate,this.layers.mask=e.layers.mask,this.visible=e.visible,this.castShadow=e.castShadow,this.receiveShadow=e.receiveShadow,this.frustumCulled=e.frustumCulled,this.renderOrder=e.renderOrder,this.animations=e.animations.slice(),this.userData=JSON.parse(JSON.stringify(e.userData)),t===!0)for(let n=0;n<e.children.length;n++){const r=e.children[n];this.add(r.clone())}return this}}pt.DEFAULT_UP=new P(0,1,0);pt.DEFAULT_MATRIX_AUTO_UPDATE=!0;pt.DEFAULT_MATRIX_WORLD_AUTO_UPDATE=!0;const yn=new P,Hn=new P,po=new P,Gn=new P,Ki=new P,$i=new P,od=new P,mo=new P,go=new P,_o=new P,yo=new Ye,xo=new Ye,vo=new Ye;class rn{constructor(e=new P,t=new P,n=new P){this.a=e,this.b=t,this.c=n}static getNormal(e,t,n,r){r.subVectors(n,t),yn.subVectors(e,t),r.cross(yn);const s=r.lengthSq();return s>0?r.multiplyScalar(1/Math.sqrt(s)):r.set(0,0,0)}static getBarycoord(e,t,n,r,s){yn.subVectors(r,t),Hn.subVectors(n,t),po.subVectors(e,t);const a=yn.dot(yn),o=yn.dot(Hn),l=yn.dot(po),c=Hn.dot(Hn),h=Hn.dot(po),u=a*c-o*o;if(u===0)return s.set(0,0,0),null;const f=1/u,p=(c*l-o*h)*f,_=(a*h-o*l)*f;return s.set(1-p-_,_,p)}static containsPoint(e,t,n,r){return this.getBarycoord(e,t,n,r,Gn)===null?!1:Gn.x>=0&&Gn.y>=0&&Gn.x+Gn.y<=1}static getInterpolation(e,t,n,r,s,a,o,l){return this.getBarycoord(e,t,n,r,Gn)===null?(l.x=0,l.y=0,"z"in l&&(l.z=0),"w"in l&&(l.w=0),null):(l.setScalar(0),l.addScaledVector(s,Gn.x),l.addScaledVector(a,Gn.y),l.addScaledVector(o,Gn.z),l)}static getInterpolatedAttribute(e,t,n,r,s,a){return yo.setScalar(0),xo.setScalar(0),vo.setScalar(0),yo.fromBufferAttribute(e,t),xo.fromBufferAttribute(e,n),vo.fromBufferAttribute(e,r),a.setScalar(0),a.addScaledVector(yo,s.x),a.addScaledVector(xo,s.y),a.addScaledVector(vo,s.z),a}static isFrontFacing(e,t,n,r){return yn.subVectors(n,t),Hn.subVectors(e,t),yn.cross(Hn).dot(r)<0}set(e,t,n){return this.a.copy(e),this.b.copy(t),this.c.copy(n),this}setFromPointsAndIndices(e,t,n,r){return this.a.copy(e[t]),this.b.copy(e[n]),this.c.copy(e[r]),this}setFromAttributeAndIndices(e,t,n,r){return this.a.fromBufferAttribute(e,t),this.b.fromBufferAttribute(e,n),this.c.fromBufferAttribute(e,r),this}clone(){return new this.constructor().copy(this)}copy(e){return this.a.copy(e.a),this.b.copy(e.b),this.c.copy(e.c),this}getArea(){return yn.subVectors(this.c,this.b),Hn.subVectors(this.a,this.b),yn.cross(Hn).length()*.5}getMidpoint(e){return e.addVectors(this.a,this.b).add(this.c).multiplyScalar(1/3)}getNormal(e){return rn.getNormal(this.a,this.b,this.c,e)}getPlane(e){return e.setFromCoplanarPoints(this.a,this.b,this.c)}getBarycoord(e,t){return rn.getBarycoord(e,this.a,this.b,this.c,t)}getInterpolation(e,t,n,r,s){return rn.getInterpolation(e,this.a,this.b,this.c,t,n,r,s)}containsPoint(e){return rn.containsPoint(e,this.a,this.b,this.c)}isFrontFacing(e){return rn.isFrontFacing(this.a,this.b,this.c,e)}intersectsBox(e){return e.intersectsTriangle(this)}closestPointToPoint(e,t){const n=this.a,r=this.b,s=this.c;let a,o;Ki.subVectors(r,n),$i.subVectors(s,n),mo.subVectors(e,n);const l=Ki.dot(mo),c=$i.dot(mo);if(l<=0&&c<=0)return t.copy(n);go.subVectors(e,r);const h=Ki.dot(go),u=$i.dot(go);if(h>=0&&u<=h)return t.copy(r);const f=l*u-h*c;if(f<=0&&l>=0&&h<=0)return a=l/(l-h),t.copy(n).addScaledVector(Ki,a);_o.subVectors(e,s);const p=Ki.dot(_o),_=$i.dot(_o);if(_>=0&&p<=_)return t.copy(s);const y=p*c-l*_;if(y<=0&&c>=0&&_<=0)return o=c/(c-_),t.copy(n).addScaledVector($i,o);const g=h*_-p*u;if(g<=0&&u-h>=0&&p-_>=0)return od.subVectors(s,r),o=(u-h)/(u-h+(p-_)),t.copy(r).addScaledVector(od,o);const m=1/(g+y+f);return a=y*m,o=f*m,t.copy(n).addScaledVector(Ki,a).addScaledVector($i,o)}equals(e){return e.a.equals(this.a)&&e.b.equals(this.b)&&e.c.equals(this.c)}}const Hu={aliceblue:15792383,antiquewhite:16444375,aqua:65535,aquamarine:8388564,azure:15794175,beige:16119260,bisque:16770244,black:0,blanchedalmond:16772045,blue:255,blueviolet:9055202,brown:10824234,burlywood:14596231,cadetblue:6266528,chartreuse:8388352,chocolate:13789470,coral:16744272,cornflowerblue:6591981,cornsilk:16775388,crimson:14423100,cyan:65535,darkblue:139,darkcyan:35723,darkgoldenrod:12092939,darkgray:11119017,darkgreen:25600,darkgrey:11119017,darkkhaki:12433259,darkmagenta:9109643,darkolivegreen:5597999,darkorange:16747520,darkorchid:10040012,darkred:9109504,darksalmon:15308410,darkseagreen:9419919,darkslateblue:4734347,darkslategray:3100495,darkslategrey:3100495,darkturquoise:52945,darkviolet:9699539,deeppink:16716947,deepskyblue:49151,dimgray:6908265,dimgrey:6908265,dodgerblue:2003199,firebrick:11674146,floralwhite:16775920,forestgreen:2263842,fuchsia:16711935,gainsboro:14474460,ghostwhite:16316671,gold:16766720,goldenrod:14329120,gray:8421504,green:32768,greenyellow:11403055,grey:8421504,honeydew:15794160,hotpink:16738740,indianred:13458524,indigo:4915330,ivory:16777200,khaki:15787660,lavender:15132410,lavenderblush:16773365,lawngreen:8190976,lemonchiffon:16775885,lightblue:11393254,lightcoral:15761536,lightcyan:14745599,lightgoldenrodyellow:16448210,lightgray:13882323,lightgreen:9498256,lightgrey:13882323,lightpink:16758465,lightsalmon:16752762,lightseagreen:2142890,lightskyblue:8900346,lightslategray:7833753,lightslategrey:7833753,lightsteelblue:11584734,lightyellow:16777184,lime:65280,limegreen:3329330,linen:16445670,magenta:16711935,maroon:8388608,mediumaquamarine:6737322,mediumblue:205,mediumorchid:12211667,mediumpurple:9662683,mediumseagreen:3978097,mediumslateblue:8087790,mediumspringgreen:64154,mediumturquoise:4772300,mediumvioletred:13047173,midnightblue:1644912,mintcream:16121850,mistyrose:16770273,moccasin:16770229,navajowhite:16768685,navy:128,oldlace:16643558,olive:8421376,olivedrab:7048739,orange:16753920,orangered:16729344,orchid:14315734,palegoldenrod:15657130,palegreen:10025880,paleturquoise:11529966,palevioletred:14381203,papayawhip:16773077,peachpuff:16767673,peru:13468991,pink:16761035,plum:14524637,powderblue:11591910,purple:8388736,rebeccapurple:6697881,red:16711680,rosybrown:12357519,royalblue:4286945,saddlebrown:9127187,salmon:16416882,sandybrown:16032864,seagreen:3050327,seashell:16774638,sienna:10506797,silver:12632256,skyblue:8900331,slateblue:6970061,slategray:7372944,slategrey:7372944,snow:16775930,springgreen:65407,steelblue:4620980,tan:13808780,teal:32896,thistle:14204888,tomato:16737095,turquoise:4251856,violet:15631086,wheat:16113331,white:16777215,whitesmoke:16119285,yellow:16776960,yellowgreen:10145074},ci={h:0,s:0,l:0},Xs={h:0,s:0,l:0};function Mo(i,e,t){return t<0&&(t+=1),t>1&&(t-=1),t<1/6?i+(e-i)*6*t:t<1/2?e:t<2/3?i+(e-i)*6*(2/3-t):i}class Ee{constructor(e,t,n){return this.isColor=!0,this.r=1,this.g=1,this.b=1,this.set(e,t,n)}set(e,t,n){if(t===void 0&&n===void 0){const r=e;r&&r.isColor?this.copy(r):typeof r=="number"?this.setHex(r):typeof r=="string"&&this.setStyle(r)}else this.setRGB(e,t,n);return this}setScalar(e){return this.r=e,this.g=e,this.b=e,this}setHex(e,t=Et){return e=Math.floor(e),this.r=(e>>16&255)/255,this.g=(e>>8&255)/255,this.b=(e&255)/255,Je.colorSpaceToWorking(this,t),this}setRGB(e,t,n,r=Je.workingColorSpace){return this.r=e,this.g=t,this.b=n,Je.colorSpaceToWorking(this,r),this}setHSL(e,t,n,r=Je.workingColorSpace){if(e=ec(e,1),t=Xe(t,0,1),n=Xe(n,0,1),t===0)this.r=this.g=this.b=n;else{const s=n<=.5?n*(1+t):n+t-n*t,a=2*n-s;this.r=Mo(a,s,e+1/3),this.g=Mo(a,s,e),this.b=Mo(a,s,e-1/3)}return Je.colorSpaceToWorking(this,r),this}setStyle(e,t=Et){function n(s){s!==void 0&&parseFloat(s)<1&&console.warn("THREE.Color: Alpha component of "+e+" will be ignored.")}let r;if(r=/^(\w+)\(([^\)]*)\)/.exec(e)){let s;const a=r[1],o=r[2];switch(a){case"rgb":case"rgba":if(s=/^\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(s[4]),this.setRGB(Math.min(255,parseInt(s[1],10))/255,Math.min(255,parseInt(s[2],10))/255,Math.min(255,parseInt(s[3],10))/255,t);if(s=/^\s*(\d+)\%\s*,\s*(\d+)\%\s*,\s*(\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(s[4]),this.setRGB(Math.min(100,parseInt(s[1],10))/100,Math.min(100,parseInt(s[2],10))/100,Math.min(100,parseInt(s[3],10))/100,t);break;case"hsl":case"hsla":if(s=/^\s*(\d*\.?\d+)\s*,\s*(\d*\.?\d+)\%\s*,\s*(\d*\.?\d+)\%\s*(?:,\s*(\d*\.?\d+)\s*)?$/.exec(o))return n(s[4]),this.setHSL(parseFloat(s[1])/360,parseFloat(s[2])/100,parseFloat(s[3])/100,t);break;default:console.warn("THREE.Color: Unknown color model "+e)}}else if(r=/^\#([A-Fa-f\d]+)$/.exec(e)){const s=r[1],a=s.length;if(a===3)return this.setRGB(parseInt(s.charAt(0),16)/15,parseInt(s.charAt(1),16)/15,parseInt(s.charAt(2),16)/15,t);if(a===6)return this.setHex(parseInt(s,16),t);console.warn("THREE.Color: Invalid hex color "+e)}else if(e&&e.length>0)return this.setColorName(e,t);return this}setColorName(e,t=Et){const n=Hu[e.toLowerCase()];return n!==void 0?this.setHex(n,t):console.warn("THREE.Color: Unknown color "+e),this}clone(){return new this.constructor(this.r,this.g,this.b)}copy(e){return this.r=e.r,this.g=e.g,this.b=e.b,this}copySRGBToLinear(e){return this.r=Jn(e.r),this.g=Jn(e.g),this.b=Jn(e.b),this}copyLinearToSRGB(e){return this.r=yr(e.r),this.g=yr(e.g),this.b=yr(e.b),this}convertSRGBToLinear(){return this.copySRGBToLinear(this),this}convertLinearToSRGB(){return this.copyLinearToSRGB(this),this}getHex(e=Et){return Je.workingToColorSpace(Ft.copy(this),e),Math.round(Xe(Ft.r*255,0,255))*65536+Math.round(Xe(Ft.g*255,0,255))*256+Math.round(Xe(Ft.b*255,0,255))}getHexString(e=Et){return("000000"+this.getHex(e).toString(16)).slice(-6)}getHSL(e,t=Je.workingColorSpace){Je.workingToColorSpace(Ft.copy(this),t);const n=Ft.r,r=Ft.g,s=Ft.b,a=Math.max(n,r,s),o=Math.min(n,r,s);let l,c;const h=(o+a)/2;if(o===a)l=0,c=0;else{const u=a-o;switch(c=h<=.5?u/(a+o):u/(2-a-o),a){case n:l=(r-s)/u+(r<s?6:0);break;case r:l=(s-n)/u+2;break;case s:l=(n-r)/u+4;break}l/=6}return e.h=l,e.s=c,e.l=h,e}getRGB(e,t=Je.workingColorSpace){return Je.workingToColorSpace(Ft.copy(this),t),e.r=Ft.r,e.g=Ft.g,e.b=Ft.b,e}getStyle(e=Et){Je.workingToColorSpace(Ft.copy(this),e);const t=Ft.r,n=Ft.g,r=Ft.b;return e!==Et?`color(${e} ${t.toFixed(3)} ${n.toFixed(3)} ${r.toFixed(3)})`:`rgb(${Math.round(t*255)},${Math.round(n*255)},${Math.round(r*255)})`}offsetHSL(e,t,n){return this.getHSL(ci),this.setHSL(ci.h+e,ci.s+t,ci.l+n)}add(e){return this.r+=e.r,this.g+=e.g,this.b+=e.b,this}addColors(e,t){return this.r=e.r+t.r,this.g=e.g+t.g,this.b=e.b+t.b,this}addScalar(e){return this.r+=e,this.g+=e,this.b+=e,this}sub(e){return this.r=Math.max(0,this.r-e.r),this.g=Math.max(0,this.g-e.g),this.b=Math.max(0,this.b-e.b),this}multiply(e){return this.r*=e.r,this.g*=e.g,this.b*=e.b,this}multiplyScalar(e){return this.r*=e,this.g*=e,this.b*=e,this}lerp(e,t){return this.r+=(e.r-this.r)*t,this.g+=(e.g-this.g)*t,this.b+=(e.b-this.b)*t,this}lerpColors(e,t,n){return this.r=e.r+(t.r-e.r)*n,this.g=e.g+(t.g-e.g)*n,this.b=e.b+(t.b-e.b)*n,this}lerpHSL(e,t){this.getHSL(ci),e.getHSL(Xs);const n=ls(ci.h,Xs.h,t),r=ls(ci.s,Xs.s,t),s=ls(ci.l,Xs.l,t);return this.setHSL(n,r,s),this}setFromVector3(e){return this.r=e.x,this.g=e.y,this.b=e.z,this}applyMatrix3(e){const t=this.r,n=this.g,r=this.b,s=e.elements;return this.r=s[0]*t+s[3]*n+s[6]*r,this.g=s[1]*t+s[4]*n+s[7]*r,this.b=s[2]*t+s[5]*n+s[8]*r,this}equals(e){return e.r===this.r&&e.g===this.g&&e.b===this.b}fromArray(e,t=0){return this.r=e[t],this.g=e[t+1],this.b=e[t+2],this}toArray(e=[],t=0){return e[t]=this.r,e[t+1]=this.g,e[t+2]=this.b,e}fromBufferAttribute(e,t){return this.r=e.getX(t),this.g=e.getY(t),this.b=e.getZ(t),this}toJSON(){return this.getHex()}*[Symbol.iterator](){yield this.r,yield this.g,yield this.b}}const Ft=new Ee;Ee.NAMES=Hu;let Mp=0;class hn extends Oi{constructor(){super(),this.isMaterial=!0,Object.defineProperty(this,"id",{value:Mp++}),this.uuid=bn(),this.name="",this.type="Material",this.blending=mr,this.side=ei,this.vertexColors=!1,this.opacity=1,this.transparent=!1,this.alphaHash=!1,this.blendSrc=jo,this.blendDst=qo,this.blendEquation=Ci,this.blendSrcAlpha=null,this.blendDstAlpha=null,this.blendEquationAlpha=null,this.blendColor=new Ee(0,0,0),this.blendAlpha=0,this.depthFunc=br,this.depthTest=!0,this.depthWrite=!0,this.stencilWriteMask=255,this.stencilFunc=qc,this.stencilRef=0,this.stencilFuncMask=255,this.stencilFail=Hi,this.stencilZFail=Hi,this.stencilZPass=Hi,this.stencilWrite=!1,this.clippingPlanes=null,this.clipIntersection=!1,this.clipShadows=!1,this.shadowSide=null,this.colorWrite=!0,this.precision=null,this.polygonOffset=!1,this.polygonOffsetFactor=0,this.polygonOffsetUnits=0,this.dithering=!1,this.alphaToCoverage=!1,this.premultipliedAlpha=!1,this.forceSinglePass=!1,this.allowOverride=!0,this.visible=!0,this.toneMapped=!0,this.userData={},this.version=0,this._alphaTest=0}get alphaTest(){return this._alphaTest}set alphaTest(e){this._alphaTest>0!=e>0&&this.version++,this._alphaTest=e}onBeforeRender(){}onBeforeCompile(){}customProgramCacheKey(){return this.onBeforeCompile.toString()}setValues(e){if(e!==void 0)for(const t in e){const n=e[t];if(n===void 0){console.warn(`THREE.Material: parameter '${t}' has value of undefined.`);continue}const r=this[t];if(r===void 0){console.warn(`THREE.Material: '${t}' is not a property of THREE.${this.type}.`);continue}r&&r.isColor?r.set(n):r&&r.isVector3&&n&&n.isVector3?r.copy(n):this[t]=n}}toJSON(e){const t=e===void 0||typeof e=="string";t&&(e={textures:{},images:{}});const n={metadata:{version:4.7,type:"Material",generator:"Material.toJSON"}};n.uuid=this.uuid,n.type=this.type,this.name!==""&&(n.name=this.name),this.color&&this.color.isColor&&(n.color=this.color.getHex()),this.roughness!==void 0&&(n.roughness=this.roughness),this.metalness!==void 0&&(n.metalness=this.metalness),this.sheen!==void 0&&(n.sheen=this.sheen),this.sheenColor&&this.sheenColor.isColor&&(n.sheenColor=this.sheenColor.getHex()),this.sheenRoughness!==void 0&&(n.sheenRoughness=this.sheenRoughness),this.emissive&&this.emissive.isColor&&(n.emissive=this.emissive.getHex()),this.emissiveIntensity!==void 0&&this.emissiveIntensity!==1&&(n.emissiveIntensity=this.emissiveIntensity),this.specular&&this.specular.isColor&&(n.specular=this.specular.getHex()),this.specularIntensity!==void 0&&(n.specularIntensity=this.specularIntensity),this.specularColor&&this.specularColor.isColor&&(n.specularColor=this.specularColor.getHex()),this.shininess!==void 0&&(n.shininess=this.shininess),this.clearcoat!==void 0&&(n.clearcoat=this.clearcoat),this.clearcoatRoughness!==void 0&&(n.clearcoatRoughness=this.clearcoatRoughness),this.clearcoatMap&&this.clearcoatMap.isTexture&&(n.clearcoatMap=this.clearcoatMap.toJSON(e).uuid),this.clearcoatRoughnessMap&&this.clearcoatRoughnessMap.isTexture&&(n.clearcoatRoughnessMap=this.clearcoatRoughnessMap.toJSON(e).uuid),this.clearcoatNormalMap&&this.clearcoatNormalMap.isTexture&&(n.clearcoatNormalMap=this.clearcoatNormalMap.toJSON(e).uuid,n.clearcoatNormalScale=this.clearcoatNormalScale.toArray()),this.dispersion!==void 0&&(n.dispersion=this.dispersion),this.iridescence!==void 0&&(n.iridescence=this.iridescence),this.iridescenceIOR!==void 0&&(n.iridescenceIOR=this.iridescenceIOR),this.iridescenceThicknessRange!==void 0&&(n.iridescenceThicknessRange=this.iridescenceThicknessRange),this.iridescenceMap&&this.iridescenceMap.isTexture&&(n.iridescenceMap=this.iridescenceMap.toJSON(e).uuid),this.iridescenceThicknessMap&&this.iridescenceThicknessMap.isTexture&&(n.iridescenceThicknessMap=this.iridescenceThicknessMap.toJSON(e).uuid),this.anisotropy!==void 0&&(n.anisotropy=this.anisotropy),this.anisotropyRotation!==void 0&&(n.anisotropyRotation=this.anisotropyRotation),this.anisotropyMap&&this.anisotropyMap.isTexture&&(n.anisotropyMap=this.anisotropyMap.toJSON(e).uuid),this.map&&this.map.isTexture&&(n.map=this.map.toJSON(e).uuid),this.matcap&&this.matcap.isTexture&&(n.matcap=this.matcap.toJSON(e).uuid),this.alphaMap&&this.alphaMap.isTexture&&(n.alphaMap=this.alphaMap.toJSON(e).uuid),this.lightMap&&this.lightMap.isTexture&&(n.lightMap=this.lightMap.toJSON(e).uuid,n.lightMapIntensity=this.lightMapIntensity),this.aoMap&&this.aoMap.isTexture&&(n.aoMap=this.aoMap.toJSON(e).uuid,n.aoMapIntensity=this.aoMapIntensity),this.bumpMap&&this.bumpMap.isTexture&&(n.bumpMap=this.bumpMap.toJSON(e).uuid,n.bumpScale=this.bumpScale),this.normalMap&&this.normalMap.isTexture&&(n.normalMap=this.normalMap.toJSON(e).uuid,n.normalMapType=this.normalMapType,n.normalScale=this.normalScale.toArray()),this.displacementMap&&this.displacementMap.isTexture&&(n.displacementMap=this.displacementMap.toJSON(e).uuid,n.displacementScale=this.displacementScale,n.displacementBias=this.displacementBias),this.roughnessMap&&this.roughnessMap.isTexture&&(n.roughnessMap=this.roughnessMap.toJSON(e).uuid),this.metalnessMap&&this.metalnessMap.isTexture&&(n.metalnessMap=this.metalnessMap.toJSON(e).uuid),this.emissiveMap&&this.emissiveMap.isTexture&&(n.emissiveMap=this.emissiveMap.toJSON(e).uuid),this.specularMap&&this.specularMap.isTexture&&(n.specularMap=this.specularMap.toJSON(e).uuid),this.specularIntensityMap&&this.specularIntensityMap.isTexture&&(n.specularIntensityMap=this.specularIntensityMap.toJSON(e).uuid),this.specularColorMap&&this.specularColorMap.isTexture&&(n.specularColorMap=this.specularColorMap.toJSON(e).uuid),this.envMap&&this.envMap.isTexture&&(n.envMap=this.envMap.toJSON(e).uuid,this.combine!==void 0&&(n.combine=this.combine)),this.envMapRotation!==void 0&&(n.envMapRotation=this.envMapRotation.toArray()),this.envMapIntensity!==void 0&&(n.envMapIntensity=this.envMapIntensity),this.reflectivity!==void 0&&(n.reflectivity=this.reflectivity),this.refractionRatio!==void 0&&(n.refractionRatio=this.refractionRatio),this.gradientMap&&this.gradientMap.isTexture&&(n.gradientMap=this.gradientMap.toJSON(e).uuid),this.transmission!==void 0&&(n.transmission=this.transmission),this.transmissionMap&&this.transmissionMap.isTexture&&(n.transmissionMap=this.transmissionMap.toJSON(e).uuid),this.thickness!==void 0&&(n.thickness=this.thickness),this.thicknessMap&&this.thicknessMap.isTexture&&(n.thicknessMap=this.thicknessMap.toJSON(e).uuid),this.attenuationDistance!==void 0&&this.attenuationDistance!==1/0&&(n.attenuationDistance=this.attenuationDistance),this.attenuationColor!==void 0&&(n.attenuationColor=this.attenuationColor.getHex()),this.size!==void 0&&(n.size=this.size),this.shadowSide!==null&&(n.shadowSide=this.shadowSide),this.sizeAttenuation!==void 0&&(n.sizeAttenuation=this.sizeAttenuation),this.blending!==mr&&(n.blending=this.blending),this.side!==ei&&(n.side=this.side),this.vertexColors===!0&&(n.vertexColors=!0),this.opacity<1&&(n.opacity=this.opacity),this.transparent===!0&&(n.transparent=!0),this.blendSrc!==jo&&(n.blendSrc=this.blendSrc),this.blendDst!==qo&&(n.blendDst=this.blendDst),this.blendEquation!==Ci&&(n.blendEquation=this.blendEquation),this.blendSrcAlpha!==null&&(n.blendSrcAlpha=this.blendSrcAlpha),this.blendDstAlpha!==null&&(n.blendDstAlpha=this.blendDstAlpha),this.blendEquationAlpha!==null&&(n.blendEquationAlpha=this.blendEquationAlpha),this.blendColor&&this.blendColor.isColor&&(n.blendColor=this.blendColor.getHex()),this.blendAlpha!==0&&(n.blendAlpha=this.blendAlpha),this.depthFunc!==br&&(n.depthFunc=this.depthFunc),this.depthTest===!1&&(n.depthTest=this.depthTest),this.depthWrite===!1&&(n.depthWrite=this.depthWrite),this.colorWrite===!1&&(n.colorWrite=this.colorWrite),this.stencilWriteMask!==255&&(n.stencilWriteMask=this.stencilWriteMask),this.stencilFunc!==qc&&(n.stencilFunc=this.stencilFunc),this.stencilRef!==0&&(n.stencilRef=this.stencilRef),this.stencilFuncMask!==255&&(n.stencilFuncMask=this.stencilFuncMask),this.stencilFail!==Hi&&(n.stencilFail=this.stencilFail),this.stencilZFail!==Hi&&(n.stencilZFail=this.stencilZFail),this.stencilZPass!==Hi&&(n.stencilZPass=this.stencilZPass),this.stencilWrite===!0&&(n.stencilWrite=this.stencilWrite),this.rotation!==void 0&&this.rotation!==0&&(n.rotation=this.rotation),this.polygonOffset===!0&&(n.polygonOffset=!0),this.polygonOffsetFactor!==0&&(n.polygonOffsetFactor=this.polygonOffsetFactor),this.polygonOffsetUnits!==0&&(n.polygonOffsetUnits=this.polygonOffsetUnits),this.linewidth!==void 0&&this.linewidth!==1&&(n.linewidth=this.linewidth),this.dashSize!==void 0&&(n.dashSize=this.dashSize),this.gapSize!==void 0&&(n.gapSize=this.gapSize),this.scale!==void 0&&(n.scale=this.scale),this.dithering===!0&&(n.dithering=!0),this.alphaTest>0&&(n.alphaTest=this.alphaTest),this.alphaHash===!0&&(n.alphaHash=!0),this.alphaToCoverage===!0&&(n.alphaToCoverage=!0),this.premultipliedAlpha===!0&&(n.premultipliedAlpha=!0),this.forceSinglePass===!0&&(n.forceSinglePass=!0),this.wireframe===!0&&(n.wireframe=!0),this.wireframeLinewidth>1&&(n.wireframeLinewidth=this.wireframeLinewidth),this.wireframeLinecap!=="round"&&(n.wireframeLinecap=this.wireframeLinecap),this.wireframeLinejoin!=="round"&&(n.wireframeLinejoin=this.wireframeLinejoin),this.flatShading===!0&&(n.flatShading=!0),this.visible===!1&&(n.visible=!1),this.toneMapped===!1&&(n.toneMapped=!1),this.fog===!1&&(n.fog=!1),Object.keys(this.userData).length>0&&(n.userData=this.userData);function r(s){const a=[];for(const o in s){const l=s[o];delete l.metadata,a.push(l)}return a}if(t){const s=r(e.textures),a=r(e.images);s.length>0&&(n.textures=s),a.length>0&&(n.images=a)}return n}clone(){return new this.constructor().copy(this)}copy(e){this.name=e.name,this.blending=e.blending,this.side=e.side,this.vertexColors=e.vertexColors,this.opacity=e.opacity,this.transparent=e.transparent,this.blendSrc=e.blendSrc,this.blendDst=e.blendDst,this.blendEquation=e.blendEquation,this.blendSrcAlpha=e.blendSrcAlpha,this.blendDstAlpha=e.blendDstAlpha,this.blendEquationAlpha=e.blendEquationAlpha,this.blendColor.copy(e.blendColor),this.blendAlpha=e.blendAlpha,this.depthFunc=e.depthFunc,this.depthTest=e.depthTest,this.depthWrite=e.depthWrite,this.stencilWriteMask=e.stencilWriteMask,this.stencilFunc=e.stencilFunc,this.stencilRef=e.stencilRef,this.stencilFuncMask=e.stencilFuncMask,this.stencilFail=e.stencilFail,this.stencilZFail=e.stencilZFail,this.stencilZPass=e.stencilZPass,this.stencilWrite=e.stencilWrite;const t=e.clippingPlanes;let n=null;if(t!==null){const r=t.length;n=new Array(r);for(let s=0;s!==r;++s)n[s]=t[s].clone()}return this.clippingPlanes=n,this.clipIntersection=e.clipIntersection,this.clipShadows=e.clipShadows,this.shadowSide=e.shadowSide,this.colorWrite=e.colorWrite,this.precision=e.precision,this.polygonOffset=e.polygonOffset,this.polygonOffsetFactor=e.polygonOffsetFactor,this.polygonOffsetUnits=e.polygonOffsetUnits,this.dithering=e.dithering,this.alphaTest=e.alphaTest,this.alphaHash=e.alphaHash,this.alphaToCoverage=e.alphaToCoverage,this.premultipliedAlpha=e.premultipliedAlpha,this.forceSinglePass=e.forceSinglePass,this.visible=e.visible,this.toneMapped=e.toneMapped,this.userData=JSON.parse(JSON.stringify(e.userData)),this}dispose(){this.dispatchEvent({type:"dispose"})}set needsUpdate(e){e===!0&&this.version++}}class Kn extends hn{constructor(e){super(),this.isMeshBasicMaterial=!0,this.type="MeshBasicMaterial",this.color=new Ee(16777215),this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new pn,this.combine=Xl,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.specularMap=e.specularMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.combine=e.combine,this.reflectivity=e.reflectivity,this.refractionRatio=e.refractionRatio,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.fog=e.fog,this}}const qn=bp();function bp(){const i=new ArrayBuffer(4),e=new Float32Array(i),t=new Uint32Array(i),n=new Uint32Array(512),r=new Uint32Array(512);for(let l=0;l<256;++l){const c=l-127;c<-27?(n[l]=0,n[l|256]=32768,r[l]=24,r[l|256]=24):c<-14?(n[l]=1024>>-c-14,n[l|256]=1024>>-c-14|32768,r[l]=-c-1,r[l|256]=-c-1):c<=15?(n[l]=c+15<<10,n[l|256]=c+15<<10|32768,r[l]=13,r[l|256]=13):c<128?(n[l]=31744,n[l|256]=64512,r[l]=24,r[l|256]=24):(n[l]=31744,n[l|256]=64512,r[l]=13,r[l|256]=13)}const s=new Uint32Array(2048),a=new Uint32Array(64),o=new Uint32Array(64);for(let l=1;l<1024;++l){let c=l<<13,h=0;for(;(c&8388608)===0;)c<<=1,h-=8388608;c&=-8388609,h+=947912704,s[l]=c|h}for(let l=1024;l<2048;++l)s[l]=939524096+(l-1024<<13);for(let l=1;l<31;++l)a[l]=l<<23;a[31]=1199570944,a[32]=2147483648;for(let l=33;l<63;++l)a[l]=2147483648+(l-32<<23);a[63]=3347054592;for(let l=1;l<64;++l)l!==32&&(o[l]=1024);return{floatView:e,uint32View:t,baseTable:n,shiftTable:r,mantissaTable:s,exponentTable:a,offsetTable:o}}function Sp(i){Math.abs(i)>65504&&console.warn("THREE.DataUtils.toHalfFloat(): Value out of range."),i=Xe(i,-65504,65504),qn.floatView[0]=i;const e=qn.uint32View[0],t=e>>23&511;return qn.baseTable[t]+((e&8388607)>>qn.shiftTable[t])}function wp(i){const e=i>>10;return qn.uint32View[0]=qn.mantissaTable[qn.offsetTable[e]+(i&1023)]+qn.exponentTable[e],qn.floatView[0]}class ns{static toHalfFloat(e){return Sp(e)}static fromHalfFloat(e){return wp(e)}}const wt=new P,js=new xe;let Ep=0;class Ot{constructor(e,t,n=!1){if(Array.isArray(e))throw new TypeError("THREE.BufferAttribute: array should be a Typed Array.");this.isBufferAttribute=!0,Object.defineProperty(this,"id",{value:Ep++}),this.name="",this.array=e,this.itemSize=t,this.count=e!==void 0?e.length/t:0,this.normalized=n,this.usage=Cl,this.updateRanges=[],this.gpuType=$t,this.version=0}onUploadCallback(){}set needsUpdate(e){e===!0&&this.version++}setUsage(e){return this.usage=e,this}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}copy(e){return this.name=e.name,this.array=new e.array.constructor(e.array),this.itemSize=e.itemSize,this.count=e.count,this.normalized=e.normalized,this.usage=e.usage,this.gpuType=e.gpuType,this}copyAt(e,t,n){e*=this.itemSize,n*=t.itemSize;for(let r=0,s=this.itemSize;r<s;r++)this.array[e+r]=t.array[n+r];return this}copyArray(e){return this.array.set(e),this}applyMatrix3(e){if(this.itemSize===2)for(let t=0,n=this.count;t<n;t++)js.fromBufferAttribute(this,t),js.applyMatrix3(e),this.setXY(t,js.x,js.y);else if(this.itemSize===3)for(let t=0,n=this.count;t<n;t++)wt.fromBufferAttribute(this,t),wt.applyMatrix3(e),this.setXYZ(t,wt.x,wt.y,wt.z);return this}applyMatrix4(e){for(let t=0,n=this.count;t<n;t++)wt.fromBufferAttribute(this,t),wt.applyMatrix4(e),this.setXYZ(t,wt.x,wt.y,wt.z);return this}applyNormalMatrix(e){for(let t=0,n=this.count;t<n;t++)wt.fromBufferAttribute(this,t),wt.applyNormalMatrix(e),this.setXYZ(t,wt.x,wt.y,wt.z);return this}transformDirection(e){for(let t=0,n=this.count;t<n;t++)wt.fromBufferAttribute(this,t),wt.transformDirection(e),this.setXYZ(t,wt.x,wt.y,wt.z);return this}set(e,t=0){return this.array.set(e,t),this}getComponent(e,t){let n=this.array[e*this.itemSize+t];return this.normalized&&(n=vn(n,this.array)),n}setComponent(e,t,n){return this.normalized&&(n=st(n,this.array)),this.array[e*this.itemSize+t]=n,this}getX(e){let t=this.array[e*this.itemSize];return this.normalized&&(t=vn(t,this.array)),t}setX(e,t){return this.normalized&&(t=st(t,this.array)),this.array[e*this.itemSize]=t,this}getY(e){let t=this.array[e*this.itemSize+1];return this.normalized&&(t=vn(t,this.array)),t}setY(e,t){return this.normalized&&(t=st(t,this.array)),this.array[e*this.itemSize+1]=t,this}getZ(e){let t=this.array[e*this.itemSize+2];return this.normalized&&(t=vn(t,this.array)),t}setZ(e,t){return this.normalized&&(t=st(t,this.array)),this.array[e*this.itemSize+2]=t,this}getW(e){let t=this.array[e*this.itemSize+3];return this.normalized&&(t=vn(t,this.array)),t}setW(e,t){return this.normalized&&(t=st(t,this.array)),this.array[e*this.itemSize+3]=t,this}setXY(e,t,n){return e*=this.itemSize,this.normalized&&(t=st(t,this.array),n=st(n,this.array)),this.array[e+0]=t,this.array[e+1]=n,this}setXYZ(e,t,n,r){return e*=this.itemSize,this.normalized&&(t=st(t,this.array),n=st(n,this.array),r=st(r,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=r,this}setXYZW(e,t,n,r,s){return e*=this.itemSize,this.normalized&&(t=st(t,this.array),n=st(n,this.array),r=st(r,this.array),s=st(s,this.array)),this.array[e+0]=t,this.array[e+1]=n,this.array[e+2]=r,this.array[e+3]=s,this}onUpload(e){return this.onUploadCallback=e,this}clone(){return new this.constructor(this.array,this.itemSize).copy(this)}toJSON(){const e={itemSize:this.itemSize,type:this.array.constructor.name,array:Array.from(this.array),normalized:this.normalized};return this.name!==""&&(e.name=this.name),this.usage!==Cl&&(e.usage=this.usage),e}}class Gu extends Ot{constructor(e,t,n){super(new Uint16Array(e),t,n)}}class Vu extends Ot{constructor(e,t,n){super(new Uint32Array(e),t,n)}}class mt extends Ot{constructor(e,t,n){super(new Float32Array(e),t,n)}}let Tp=0;const ln=new De,bo=new pt,Zi=new P,tn=new kt,jr=new kt,Nt=new P;class yt extends Oi{constructor(){super(),this.isBufferGeometry=!0,Object.defineProperty(this,"id",{value:Tp++}),this.uuid=bn(),this.name="",this.type="BufferGeometry",this.index=null,this.indirect=null,this.attributes={},this.morphAttributes={},this.morphTargetsRelative=!1,this.groups=[],this.boundingBox=null,this.boundingSphere=null,this.drawRange={start:0,count:1/0},this.userData={}}getIndex(){return this.index}setIndex(e){return Array.isArray(e)?this.index=new(zu(e)?Vu:Gu)(e,1):this.index=e,this}setIndirect(e){return this.indirect=e,this}getIndirect(){return this.indirect}getAttribute(e){return this.attributes[e]}setAttribute(e,t){return this.attributes[e]=t,this}deleteAttribute(e){return delete this.attributes[e],this}hasAttribute(e){return this.attributes[e]!==void 0}addGroup(e,t,n=0){this.groups.push({start:e,count:t,materialIndex:n})}clearGroups(){this.groups=[]}setDrawRange(e,t){this.drawRange.start=e,this.drawRange.count=t}applyMatrix4(e){const t=this.attributes.position;t!==void 0&&(t.applyMatrix4(e),t.needsUpdate=!0);const n=this.attributes.normal;if(n!==void 0){const s=new Ve().getNormalMatrix(e);n.applyNormalMatrix(s),n.needsUpdate=!0}const r=this.attributes.tangent;return r!==void 0&&(r.transformDirection(e),r.needsUpdate=!0),this.boundingBox!==null&&this.computeBoundingBox(),this.boundingSphere!==null&&this.computeBoundingSphere(),this}applyQuaternion(e){return ln.makeRotationFromQuaternion(e),this.applyMatrix4(ln),this}rotateX(e){return ln.makeRotationX(e),this.applyMatrix4(ln),this}rotateY(e){return ln.makeRotationY(e),this.applyMatrix4(ln),this}rotateZ(e){return ln.makeRotationZ(e),this.applyMatrix4(ln),this}translate(e,t,n){return ln.makeTranslation(e,t,n),this.applyMatrix4(ln),this}scale(e,t,n){return ln.makeScale(e,t,n),this.applyMatrix4(ln),this}lookAt(e){return bo.lookAt(e),bo.updateMatrix(),this.applyMatrix4(bo.matrix),this}center(){return this.computeBoundingBox(),this.boundingBox.getCenter(Zi).negate(),this.translate(Zi.x,Zi.y,Zi.z),this}setFromPoints(e){const t=this.getAttribute("position");if(t===void 0){const n=[];for(let r=0,s=e.length;r<s;r++){const a=e[r];n.push(a.x,a.y,a.z||0)}this.setAttribute("position",new mt(n,3))}else{const n=Math.min(e.length,t.count);for(let r=0;r<n;r++){const s=e[r];t.setXYZ(r,s.x,s.y,s.z||0)}e.length>t.count&&console.warn("THREE.BufferGeometry: Buffer size too small for points data. Use .dispose() and create a new geometry."),t.needsUpdate=!0}return this}computeBoundingBox(){this.boundingBox===null&&(this.boundingBox=new kt);const e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){console.error("THREE.BufferGeometry.computeBoundingBox(): GLBufferAttribute requires a manual bounding box.",this),this.boundingBox.set(new P(-1/0,-1/0,-1/0),new P(1/0,1/0,1/0));return}if(e!==void 0){if(this.boundingBox.setFromBufferAttribute(e),t)for(let n=0,r=t.length;n<r;n++){const s=t[n];tn.setFromBufferAttribute(s),this.morphTargetsRelative?(Nt.addVectors(this.boundingBox.min,tn.min),this.boundingBox.expandByPoint(Nt),Nt.addVectors(this.boundingBox.max,tn.max),this.boundingBox.expandByPoint(Nt)):(this.boundingBox.expandByPoint(tn.min),this.boundingBox.expandByPoint(tn.max))}}else this.boundingBox.makeEmpty();(isNaN(this.boundingBox.min.x)||isNaN(this.boundingBox.min.y)||isNaN(this.boundingBox.min.z))&&console.error('THREE.BufferGeometry.computeBoundingBox(): Computed min/max have NaN values. The "position" attribute is likely to have NaN values.',this)}computeBoundingSphere(){this.boundingSphere===null&&(this.boundingSphere=new Un);const e=this.attributes.position,t=this.morphAttributes.position;if(e&&e.isGLBufferAttribute){console.error("THREE.BufferGeometry.computeBoundingSphere(): GLBufferAttribute requires a manual bounding sphere.",this),this.boundingSphere.set(new P,1/0);return}if(e){const n=this.boundingSphere.center;if(tn.setFromBufferAttribute(e),t)for(let s=0,a=t.length;s<a;s++){const o=t[s];jr.setFromBufferAttribute(o),this.morphTargetsRelative?(Nt.addVectors(tn.min,jr.min),tn.expandByPoint(Nt),Nt.addVectors(tn.max,jr.max),tn.expandByPoint(Nt)):(tn.expandByPoint(jr.min),tn.expandByPoint(jr.max))}tn.getCenter(n);let r=0;for(let s=0,a=e.count;s<a;s++)Nt.fromBufferAttribute(e,s),r=Math.max(r,n.distanceToSquared(Nt));if(t)for(let s=0,a=t.length;s<a;s++){const o=t[s],l=this.morphTargetsRelative;for(let c=0,h=o.count;c<h;c++)Nt.fromBufferAttribute(o,c),l&&(Zi.fromBufferAttribute(e,c),Nt.add(Zi)),r=Math.max(r,n.distanceToSquared(Nt))}this.boundingSphere.radius=Math.sqrt(r),isNaN(this.boundingSphere.radius)&&console.error('THREE.BufferGeometry.computeBoundingSphere(): Computed radius is NaN. The "position" attribute is likely to have NaN values.',this)}}computeTangents(){const e=this.index,t=this.attributes;if(e===null||t.position===void 0||t.normal===void 0||t.uv===void 0){console.error("THREE.BufferGeometry: .computeTangents() failed. Missing required attributes (index, position, normal or uv)");return}const n=t.position,r=t.normal,s=t.uv;this.hasAttribute("tangent")===!1&&this.setAttribute("tangent",new Ot(new Float32Array(4*n.count),4));const a=this.getAttribute("tangent"),o=[],l=[];for(let R=0;R<n.count;R++)o[R]=new P,l[R]=new P;const c=new P,h=new P,u=new P,f=new xe,p=new xe,_=new xe,y=new P,g=new P;function m(R,v,b){c.fromBufferAttribute(n,R),h.fromBufferAttribute(n,v),u.fromBufferAttribute(n,b),f.fromBufferAttribute(s,R),p.fromBufferAttribute(s,v),_.fromBufferAttribute(s,b),h.sub(c),u.sub(c),p.sub(f),_.sub(f);const A=1/(p.x*_.y-_.x*p.y);isFinite(A)&&(y.copy(h).multiplyScalar(_.y).addScaledVector(u,-p.y).multiplyScalar(A),g.copy(u).multiplyScalar(p.x).addScaledVector(h,-_.x).multiplyScalar(A),o[R].add(y),o[v].add(y),o[b].add(y),l[R].add(g),l[v].add(g),l[b].add(g))}let E=this.groups;E.length===0&&(E=[{start:0,count:e.count}]);for(let R=0,v=E.length;R<v;++R){const b=E[R],A=b.start,U=b.count;for(let z=A,B=A+U;z<B;z+=3)m(e.getX(z+0),e.getX(z+1),e.getX(z+2))}const w=new P,x=new P,T=new P,L=new P;function C(R){T.fromBufferAttribute(r,R),L.copy(T);const v=o[R];w.copy(v),w.sub(T.multiplyScalar(T.dot(v))).normalize(),x.crossVectors(L,v);const A=x.dot(l[R])<0?-1:1;a.setXYZW(R,w.x,w.y,w.z,A)}for(let R=0,v=E.length;R<v;++R){const b=E[R],A=b.start,U=b.count;for(let z=A,B=A+U;z<B;z+=3)C(e.getX(z+0)),C(e.getX(z+1)),C(e.getX(z+2))}}computeVertexNormals(){const e=this.index,t=this.getAttribute("position");if(t!==void 0){let n=this.getAttribute("normal");if(n===void 0)n=new Ot(new Float32Array(t.count*3),3),this.setAttribute("normal",n);else for(let f=0,p=n.count;f<p;f++)n.setXYZ(f,0,0,0);const r=new P,s=new P,a=new P,o=new P,l=new P,c=new P,h=new P,u=new P;if(e)for(let f=0,p=e.count;f<p;f+=3){const _=e.getX(f+0),y=e.getX(f+1),g=e.getX(f+2);r.fromBufferAttribute(t,_),s.fromBufferAttribute(t,y),a.fromBufferAttribute(t,g),h.subVectors(a,s),u.subVectors(r,s),h.cross(u),o.fromBufferAttribute(n,_),l.fromBufferAttribute(n,y),c.fromBufferAttribute(n,g),o.add(h),l.add(h),c.add(h),n.setXYZ(_,o.x,o.y,o.z),n.setXYZ(y,l.x,l.y,l.z),n.setXYZ(g,c.x,c.y,c.z)}else for(let f=0,p=t.count;f<p;f+=3)r.fromBufferAttribute(t,f+0),s.fromBufferAttribute(t,f+1),a.fromBufferAttribute(t,f+2),h.subVectors(a,s),u.subVectors(r,s),h.cross(u),n.setXYZ(f+0,h.x,h.y,h.z),n.setXYZ(f+1,h.x,h.y,h.z),n.setXYZ(f+2,h.x,h.y,h.z);this.normalizeNormals(),n.needsUpdate=!0}}normalizeNormals(){const e=this.attributes.normal;for(let t=0,n=e.count;t<n;t++)Nt.fromBufferAttribute(e,t),Nt.normalize(),e.setXYZ(t,Nt.x,Nt.y,Nt.z)}toNonIndexed(){function e(o,l){const c=o.array,h=o.itemSize,u=o.normalized,f=new c.constructor(l.length*h);let p=0,_=0;for(let y=0,g=l.length;y<g;y++){o.isInterleavedBufferAttribute?p=l[y]*o.data.stride+o.offset:p=l[y]*h;for(let m=0;m<h;m++)f[_++]=c[p++]}return new Ot(f,h,u)}if(this.index===null)return console.warn("THREE.BufferGeometry.toNonIndexed(): BufferGeometry is already non-indexed."),this;const t=new yt,n=this.index.array,r=this.attributes;for(const o in r){const l=r[o],c=e(l,n);t.setAttribute(o,c)}const s=this.morphAttributes;for(const o in s){const l=[],c=s[o];for(let h=0,u=c.length;h<u;h++){const f=c[h],p=e(f,n);l.push(p)}t.morphAttributes[o]=l}t.morphTargetsRelative=this.morphTargetsRelative;const a=this.groups;for(let o=0,l=a.length;o<l;o++){const c=a[o];t.addGroup(c.start,c.count,c.materialIndex)}return t}toJSON(){const e={metadata:{version:4.7,type:"BufferGeometry",generator:"BufferGeometry.toJSON"}};if(e.uuid=this.uuid,e.type=this.type,this.name!==""&&(e.name=this.name),Object.keys(this.userData).length>0&&(e.userData=this.userData),this.parameters!==void 0){const l=this.parameters;for(const c in l)l[c]!==void 0&&(e[c]=l[c]);return e}e.data={attributes:{}};const t=this.index;t!==null&&(e.data.index={type:t.array.constructor.name,array:Array.prototype.slice.call(t.array)});const n=this.attributes;for(const l in n){const c=n[l];e.data.attributes[l]=c.toJSON(e.data)}const r={};let s=!1;for(const l in this.morphAttributes){const c=this.morphAttributes[l],h=[];for(let u=0,f=c.length;u<f;u++){const p=c[u];h.push(p.toJSON(e.data))}h.length>0&&(r[l]=h,s=!0)}s&&(e.data.morphAttributes=r,e.data.morphTargetsRelative=this.morphTargetsRelative);const a=this.groups;a.length>0&&(e.data.groups=JSON.parse(JSON.stringify(a)));const o=this.boundingSphere;return o!==null&&(e.data.boundingSphere=o.toJSON()),e}clone(){return new this.constructor().copy(this)}copy(e){this.index=null,this.attributes={},this.morphAttributes={},this.groups=[],this.boundingBox=null,this.boundingSphere=null;const t={};this.name=e.name;const n=e.index;n!==null&&this.setIndex(n.clone());const r=e.attributes;for(const c in r){const h=r[c];this.setAttribute(c,h.clone(t))}const s=e.morphAttributes;for(const c in s){const h=[],u=s[c];for(let f=0,p=u.length;f<p;f++)h.push(u[f].clone(t));this.morphAttributes[c]=h}this.morphTargetsRelative=e.morphTargetsRelative;const a=e.groups;for(let c=0,h=a.length;c<h;c++){const u=a[c];this.addGroup(u.start,u.count,u.materialIndex)}const o=e.boundingBox;o!==null&&(this.boundingBox=o.clone());const l=e.boundingSphere;return l!==null&&(this.boundingSphere=l.clone()),this.drawRange.start=e.drawRange.start,this.drawRange.count=e.drawRange.count,this.userData=e.userData,this}dispose(){this.dispatchEvent({type:"dispose"})}}const ld=new De,Si=new Fr,qs=new Un,cd=new P,Ys=new P,Ks=new P,$s=new P,So=new P,Zs=new P,dd=new P,Js=new P;class ut extends pt{constructor(e=new yt,t=new Kn){super(),this.isMesh=!0,this.type="Mesh",this.geometry=e,this.material=t,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.count=1,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),e.morphTargetInfluences!==void 0&&(this.morphTargetInfluences=e.morphTargetInfluences.slice()),e.morphTargetDictionary!==void 0&&(this.morphTargetDictionary=Object.assign({},e.morphTargetDictionary)),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}updateMorphTargets(){const t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){const r=t[n[0]];if(r!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let s=0,a=r.length;s<a;s++){const o=r[s].name||String(s);this.morphTargetInfluences.push(0),this.morphTargetDictionary[o]=s}}}}getVertexPosition(e,t){const n=this.geometry,r=n.attributes.position,s=n.morphAttributes.position,a=n.morphTargetsRelative;t.fromBufferAttribute(r,e);const o=this.morphTargetInfluences;if(s&&o){Zs.set(0,0,0);for(let l=0,c=s.length;l<c;l++){const h=o[l],u=s[l];h!==0&&(So.fromBufferAttribute(u,e),a?Zs.addScaledVector(So,h):Zs.addScaledVector(So.sub(t),h))}t.add(Zs)}return t}raycast(e,t){const n=this.geometry,r=this.material,s=this.matrixWorld;r!==void 0&&(n.boundingSphere===null&&n.computeBoundingSphere(),qs.copy(n.boundingSphere),qs.applyMatrix4(s),Si.copy(e.ray).recast(e.near),!(qs.containsPoint(Si.origin)===!1&&(Si.intersectSphere(qs,cd)===null||Si.origin.distanceToSquared(cd)>(e.far-e.near)**2))&&(ld.copy(s).invert(),Si.copy(e.ray).applyMatrix4(ld),!(n.boundingBox!==null&&Si.intersectsBox(n.boundingBox)===!1)&&this._computeIntersections(e,t,Si)))}_computeIntersections(e,t,n){let r;const s=this.geometry,a=this.material,o=s.index,l=s.attributes.position,c=s.attributes.uv,h=s.attributes.uv1,u=s.attributes.normal,f=s.groups,p=s.drawRange;if(o!==null)if(Array.isArray(a))for(let _=0,y=f.length;_<y;_++){const g=f[_],m=a[g.materialIndex],E=Math.max(g.start,p.start),w=Math.min(o.count,Math.min(g.start+g.count,p.start+p.count));for(let x=E,T=w;x<T;x+=3){const L=o.getX(x),C=o.getX(x+1),R=o.getX(x+2);r=Qs(this,m,e,n,c,h,u,L,C,R),r&&(r.faceIndex=Math.floor(x/3),r.face.materialIndex=g.materialIndex,t.push(r))}}else{const _=Math.max(0,p.start),y=Math.min(o.count,p.start+p.count);for(let g=_,m=y;g<m;g+=3){const E=o.getX(g),w=o.getX(g+1),x=o.getX(g+2);r=Qs(this,a,e,n,c,h,u,E,w,x),r&&(r.faceIndex=Math.floor(g/3),t.push(r))}}else if(l!==void 0)if(Array.isArray(a))for(let _=0,y=f.length;_<y;_++){const g=f[_],m=a[g.materialIndex],E=Math.max(g.start,p.start),w=Math.min(l.count,Math.min(g.start+g.count,p.start+p.count));for(let x=E,T=w;x<T;x+=3){const L=x,C=x+1,R=x+2;r=Qs(this,m,e,n,c,h,u,L,C,R),r&&(r.faceIndex=Math.floor(x/3),r.face.materialIndex=g.materialIndex,t.push(r))}}else{const _=Math.max(0,p.start),y=Math.min(l.count,p.start+p.count);for(let g=_,m=y;g<m;g+=3){const E=g,w=g+1,x=g+2;r=Qs(this,a,e,n,c,h,u,E,w,x),r&&(r.faceIndex=Math.floor(g/3),t.push(r))}}}}function Ap(i,e,t,n,r,s,a,o){let l;if(e.side===jt?l=n.intersectTriangle(a,s,r,!0,o):l=n.intersectTriangle(r,s,a,e.side===ei,o),l===null)return null;Js.copy(o),Js.applyMatrix4(i.matrixWorld);const c=t.ray.origin.distanceTo(Js);return c<t.near||c>t.far?null:{distance:c,point:Js.clone(),object:i}}function Qs(i,e,t,n,r,s,a,o,l,c){i.getVertexPosition(o,Ys),i.getVertexPosition(l,Ks),i.getVertexPosition(c,$s);const h=Ap(i,e,t,n,Ys,Ks,$s,dd);if(h){const u=new P;rn.getBarycoord(dd,Ys,Ks,$s,u),r&&(h.uv=rn.getInterpolatedAttribute(r,o,l,c,u,new xe)),s&&(h.uv1=rn.getInterpolatedAttribute(s,o,l,c,u,new xe)),a&&(h.normal=rn.getInterpolatedAttribute(a,o,l,c,u,new P),h.normal.dot(n.direction)>0&&h.normal.multiplyScalar(-1));const f={a:o,b:l,c,normal:new P,materialIndex:0};rn.getNormal(Ys,Ks,$s,f.normal),h.face=f,h.barycoord=u}return h}class yi extends yt{constructor(e=1,t=1,n=1,r=1,s=1,a=1){super(),this.type="BoxGeometry",this.parameters={width:e,height:t,depth:n,widthSegments:r,heightSegments:s,depthSegments:a};const o=this;r=Math.floor(r),s=Math.floor(s),a=Math.floor(a);const l=[],c=[],h=[],u=[];let f=0,p=0;_("z","y","x",-1,-1,n,t,e,a,s,0),_("z","y","x",1,-1,n,t,-e,a,s,1),_("x","z","y",1,1,e,n,t,r,a,2),_("x","z","y",1,-1,e,n,-t,r,a,3),_("x","y","z",1,-1,e,t,n,r,s,4),_("x","y","z",-1,-1,e,t,-n,r,s,5),this.setIndex(l),this.setAttribute("position",new mt(c,3)),this.setAttribute("normal",new mt(h,3)),this.setAttribute("uv",new mt(u,2));function _(y,g,m,E,w,x,T,L,C,R,v){const b=x/C,A=T/R,U=x/2,z=T/2,B=L/2,V=C+1,G=R+1;let J=0,j=0;const re=new P;for(let le=0;le<G;le++){const Re=le*A-z;for(let Ne=0;Ne<V;Ne++){const Ze=Ne*b-U;re[y]=Ze*E,re[g]=Re*w,re[m]=B,c.push(re.x,re.y,re.z),re[y]=0,re[g]=0,re[m]=L>0?1:-1,h.push(re.x,re.y,re.z),u.push(Ne/C),u.push(1-le/R),J+=1}}for(let le=0;le<R;le++)for(let Re=0;Re<C;Re++){const Ne=f+Re+V*le,Ze=f+Re+V*(le+1),it=f+(Re+1)+V*(le+1),$=f+(Re+1)+V*le;l.push(Ne,Ze,$),l.push(Ze,it,$),j+=6}o.addGroup(p,j,v),p+=j,f+=J}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new yi(e.width,e.height,e.depth,e.widthSegments,e.heightSegments,e.depthSegments)}}function Tr(i){const e={};for(const t in i){e[t]={};for(const n in i[t]){const r=i[t][n];r&&(r.isColor||r.isMatrix3||r.isMatrix4||r.isVector2||r.isVector3||r.isVector4||r.isTexture||r.isQuaternion)?r.isRenderTargetTexture?(console.warn("UniformsUtils: Textures of render targets cannot be cloned via cloneUniforms() or mergeUniforms()."),e[t][n]=null):e[t][n]=r.clone():Array.isArray(r)?e[t][n]=r.slice():e[t][n]=r}}return e}function Vt(i){const e={};for(let t=0;t<i.length;t++){const n=Tr(i[t]);for(const r in n)e[r]=n[r]}return e}function Rp(i){const e=[];for(let t=0;t<i.length;t++)e.push(i[t].clone());return e}function Wu(i){const e=i.getRenderTarget();return e===null?i.outputColorSpace:e.isXRRenderTarget===!0?e.texture.colorSpace:Je.workingColorSpace}const Cp={clone:Tr,merge:Vt};var Pp=`void main() {
	gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}`,Ip=`void main() {
	gl_FragColor = vec4( 1.0, 0.0, 0.0, 1.0 );
}`;class ti extends hn{constructor(e){super(),this.isShaderMaterial=!0,this.type="ShaderMaterial",this.defines={},this.uniforms={},this.uniformsGroups=[],this.vertexShader=Pp,this.fragmentShader=Ip,this.linewidth=1,this.wireframe=!1,this.wireframeLinewidth=1,this.fog=!1,this.lights=!1,this.clipping=!1,this.forceSinglePass=!0,this.extensions={clipCullDistance:!1,multiDraw:!1},this.defaultAttributeValues={color:[1,1,1],uv:[0,0],uv1:[0,0]},this.index0AttributeName=void 0,this.uniformsNeedUpdate=!1,this.glslVersion=null,e!==void 0&&this.setValues(e)}copy(e){return super.copy(e),this.fragmentShader=e.fragmentShader,this.vertexShader=e.vertexShader,this.uniforms=Tr(e.uniforms),this.uniformsGroups=Rp(e.uniformsGroups),this.defines=Object.assign({},e.defines),this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.fog=e.fog,this.lights=e.lights,this.clipping=e.clipping,this.extensions=Object.assign({},e.extensions),this.glslVersion=e.glslVersion,this}toJSON(e){const t=super.toJSON(e);t.glslVersion=this.glslVersion,t.uniforms={};for(const r in this.uniforms){const a=this.uniforms[r].value;a&&a.isTexture?t.uniforms[r]={type:"t",value:a.toJSON(e).uuid}:a&&a.isColor?t.uniforms[r]={type:"c",value:a.getHex()}:a&&a.isVector2?t.uniforms[r]={type:"v2",value:a.toArray()}:a&&a.isVector3?t.uniforms[r]={type:"v3",value:a.toArray()}:a&&a.isVector4?t.uniforms[r]={type:"v4",value:a.toArray()}:a&&a.isMatrix3?t.uniforms[r]={type:"m3",value:a.toArray()}:a&&a.isMatrix4?t.uniforms[r]={type:"m4",value:a.toArray()}:t.uniforms[r]={value:a}}Object.keys(this.defines).length>0&&(t.defines=this.defines),t.vertexShader=this.vertexShader,t.fragmentShader=this.fragmentShader,t.lights=this.lights,t.clipping=this.clipping;const n={};for(const r in this.extensions)this.extensions[r]===!0&&(n[r]=!0);return Object.keys(n).length>0&&(t.extensions=n),t}}class Xu extends pt{constructor(){super(),this.isCamera=!0,this.type="Camera",this.matrixWorldInverse=new De,this.projectionMatrix=new De,this.projectionMatrixInverse=new De,this.coordinateSystem=Ln,this._reversedDepth=!1}get reversedDepth(){return this._reversedDepth}copy(e,t){return super.copy(e,t),this.matrixWorldInverse.copy(e.matrixWorldInverse),this.projectionMatrix.copy(e.projectionMatrix),this.projectionMatrixInverse.copy(e.projectionMatrixInverse),this.coordinateSystem=e.coordinateSystem,this}getWorldDirection(e){return super.getWorldDirection(e).negate()}updateMatrixWorld(e){super.updateMatrixWorld(e),this.matrixWorldInverse.copy(this.matrixWorld).invert()}updateWorldMatrix(e,t){super.updateWorldMatrix(e,t),this.matrixWorldInverse.copy(this.matrixWorld).invert()}clone(){return new this.constructor().copy(this)}}const di=new P,ud=new xe,hd=new xe;class Xt extends Xu{constructor(e=50,t=1,n=.1,r=2e3){super(),this.isPerspectiveCamera=!0,this.type="PerspectiveCamera",this.fov=e,this.zoom=1,this.near=n,this.far=r,this.focus=10,this.aspect=t,this.view=null,this.filmGauge=35,this.filmOffset=0,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.fov=e.fov,this.zoom=e.zoom,this.near=e.near,this.far=e.far,this.focus=e.focus,this.aspect=e.aspect,this.view=e.view===null?null:Object.assign({},e.view),this.filmGauge=e.filmGauge,this.filmOffset=e.filmOffset,this}setFocalLength(e){const t=.5*this.getFilmHeight()/e;this.fov=Er*2*Math.atan(t),this.updateProjectionMatrix()}getFocalLength(){const e=Math.tan(gr*.5*this.fov);return .5*this.getFilmHeight()/e}getEffectiveFOV(){return Er*2*Math.atan(Math.tan(gr*.5*this.fov)/this.zoom)}getFilmWidth(){return this.filmGauge*Math.min(this.aspect,1)}getFilmHeight(){return this.filmGauge/Math.max(this.aspect,1)}getViewBounds(e,t,n){di.set(-1,-1,.5).applyMatrix4(this.projectionMatrixInverse),t.set(di.x,di.y).multiplyScalar(-e/di.z),di.set(1,1,.5).applyMatrix4(this.projectionMatrixInverse),n.set(di.x,di.y).multiplyScalar(-e/di.z)}getViewSize(e,t){return this.getViewBounds(e,ud,hd),t.subVectors(hd,ud)}setViewOffset(e,t,n,r,s,a){this.aspect=e/t,this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=r,this.view.width=s,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){const e=this.near;let t=e*Math.tan(gr*.5*this.fov)/this.zoom,n=2*t,r=this.aspect*n,s=-.5*r;const a=this.view;if(this.view!==null&&this.view.enabled){const l=a.fullWidth,c=a.fullHeight;s+=a.offsetX*r/l,t-=a.offsetY*n/c,r*=a.width/l,n*=a.height/c}const o=this.filmOffset;o!==0&&(s+=e*o/this.getFilmWidth()),this.projectionMatrix.makePerspective(s,s+r,t,t-n,e,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){const t=super.toJSON(e);return t.object.fov=this.fov,t.object.zoom=this.zoom,t.object.near=this.near,t.object.far=this.far,t.object.focus=this.focus,t.object.aspect=this.aspect,this.view!==null&&(t.object.view=Object.assign({},this.view)),t.object.filmGauge=this.filmGauge,t.object.filmOffset=this.filmOffset,t}}const Ji=-90,Qi=1;class Lp extends pt{constructor(e,t,n){super(),this.type="CubeCamera",this.renderTarget=n,this.coordinateSystem=null,this.activeMipmapLevel=0;const r=new Xt(Ji,Qi,e,t);r.layers=this.layers,this.add(r);const s=new Xt(Ji,Qi,e,t);s.layers=this.layers,this.add(s);const a=new Xt(Ji,Qi,e,t);a.layers=this.layers,this.add(a);const o=new Xt(Ji,Qi,e,t);o.layers=this.layers,this.add(o);const l=new Xt(Ji,Qi,e,t);l.layers=this.layers,this.add(l);const c=new Xt(Ji,Qi,e,t);c.layers=this.layers,this.add(c)}updateCoordinateSystem(){const e=this.coordinateSystem,t=this.children.concat(),[n,r,s,a,o,l]=t;for(const c of t)this.remove(c);if(e===Ln)n.up.set(0,1,0),n.lookAt(1,0,0),r.up.set(0,1,0),r.lookAt(-1,0,0),s.up.set(0,0,-1),s.lookAt(0,1,0),a.up.set(0,0,1),a.lookAt(0,-1,0),o.up.set(0,1,0),o.lookAt(0,0,1),l.up.set(0,1,0),l.lookAt(0,0,-1);else if(e===Ua)n.up.set(0,-1,0),n.lookAt(-1,0,0),r.up.set(0,-1,0),r.lookAt(1,0,0),s.up.set(0,0,1),s.lookAt(0,1,0),a.up.set(0,0,-1),a.lookAt(0,-1,0),o.up.set(0,-1,0),o.lookAt(0,0,1),l.up.set(0,-1,0),l.lookAt(0,0,-1);else throw new Error("THREE.CubeCamera.updateCoordinateSystem(): Invalid coordinate system: "+e);for(const c of t)this.add(c),c.updateMatrixWorld()}update(e,t){this.parent===null&&this.updateMatrixWorld();const{renderTarget:n,activeMipmapLevel:r}=this;this.coordinateSystem!==e.coordinateSystem&&(this.coordinateSystem=e.coordinateSystem,this.updateCoordinateSystem());const[s,a,o,l,c,h]=this.children,u=e.getRenderTarget(),f=e.getActiveCubeFace(),p=e.getActiveMipmapLevel(),_=e.xr.enabled;e.xr.enabled=!1;const y=n.texture.generateMipmaps;n.texture.generateMipmaps=!1,e.setRenderTarget(n,0,r),e.render(t,s),e.setRenderTarget(n,1,r),e.render(t,a),e.setRenderTarget(n,2,r),e.render(t,o),e.setRenderTarget(n,3,r),e.render(t,l),e.setRenderTarget(n,4,r),e.render(t,c),n.texture.generateMipmaps=y,e.setRenderTarget(n,5,r),e.render(t,h),e.setRenderTarget(u,f,p),e.xr.enabled=_,n.texture.needsPMREMUpdate=!0}}class ju extends Ct{constructor(e=[],t=Sr,n,r,s,a,o,l,c,h){super(e,t,n,r,s,a,o,l,c,h),this.isCubeTexture=!0,this.flipY=!1}get images(){return this.image}set images(e){this.image=e}}class Dp extends Ni{constructor(e=1,t={}){super(e,e,t),this.isWebGLCubeRenderTarget=!0;const n={width:e,height:e,depth:1},r=[n,n,n,n,n,n];this.texture=new ju(r),this._setTextureOptions(t),this.texture.isRenderTargetTexture=!0}fromEquirectangularTexture(e,t){this.texture.type=t.type,this.texture.colorSpace=t.colorSpace,this.texture.generateMipmaps=t.generateMipmaps,this.texture.minFilter=t.minFilter,this.texture.magFilter=t.magFilter;const n={uniforms:{tEquirect:{value:null}},vertexShader:`

				varying vec3 vWorldDirection;

				vec3 transformDirection( in vec3 dir, in mat4 matrix ) {

					return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );

				}

				void main() {

					vWorldDirection = transformDirection( position, modelMatrix );

					#include <begin_vertex>
					#include <project_vertex>

				}
			`,fragmentShader:`

				uniform sampler2D tEquirect;

				varying vec3 vWorldDirection;

				#include <common>

				void main() {

					vec3 direction = normalize( vWorldDirection );

					vec2 sampleUV = equirectUv( direction );

					gl_FragColor = texture2D( tEquirect, sampleUV );

				}
			`},r=new yi(5,5,5),s=new ti({name:"CubemapFromEquirect",uniforms:Tr(n.uniforms),vertexShader:n.vertexShader,fragmentShader:n.fragmentShader,side:jt,blending:fi});s.uniforms.tEquirect.value=t;const a=new ut(r,s),o=t.minFilter;return t.minFilter===Pn&&(t.minFilter=Tt),new Lp(1,10,this).update(e,a),t.minFilter=o,a.geometry.dispose(),a.material.dispose(),this}clear(e,t=!0,n=!0,r=!0){const s=e.getRenderTarget();for(let a=0;a<6;a++)e.setRenderTarget(this,a),e.clear(t,n,r);e.setRenderTarget(s)}}class At extends pt{constructor(){super(),this.isGroup=!0,this.type="Group"}}const Np={type:"move"};class wo{constructor(){this._targetRay=null,this._grip=null,this._hand=null}getHandSpace(){return this._hand===null&&(this._hand=new At,this._hand.matrixAutoUpdate=!1,this._hand.visible=!1,this._hand.joints={},this._hand.inputState={pinching:!1}),this._hand}getTargetRaySpace(){return this._targetRay===null&&(this._targetRay=new At,this._targetRay.matrixAutoUpdate=!1,this._targetRay.visible=!1,this._targetRay.hasLinearVelocity=!1,this._targetRay.linearVelocity=new P,this._targetRay.hasAngularVelocity=!1,this._targetRay.angularVelocity=new P),this._targetRay}getGripSpace(){return this._grip===null&&(this._grip=new At,this._grip.matrixAutoUpdate=!1,this._grip.visible=!1,this._grip.hasLinearVelocity=!1,this._grip.linearVelocity=new P,this._grip.hasAngularVelocity=!1,this._grip.angularVelocity=new P),this._grip}dispatchEvent(e){return this._targetRay!==null&&this._targetRay.dispatchEvent(e),this._grip!==null&&this._grip.dispatchEvent(e),this._hand!==null&&this._hand.dispatchEvent(e),this}connect(e){if(e&&e.hand){const t=this._hand;if(t)for(const n of e.hand.values())this._getHandJoint(t,n)}return this.dispatchEvent({type:"connected",data:e}),this}disconnect(e){return this.dispatchEvent({type:"disconnected",data:e}),this._targetRay!==null&&(this._targetRay.visible=!1),this._grip!==null&&(this._grip.visible=!1),this._hand!==null&&(this._hand.visible=!1),this}update(e,t,n){let r=null,s=null,a=null;const o=this._targetRay,l=this._grip,c=this._hand;if(e&&t.session.visibilityState!=="visible-blurred"){if(c&&e.hand){a=!0;for(const y of e.hand.values()){const g=t.getJointPose(y,n),m=this._getHandJoint(c,y);g!==null&&(m.matrix.fromArray(g.transform.matrix),m.matrix.decompose(m.position,m.rotation,m.scale),m.matrixWorldNeedsUpdate=!0,m.jointRadius=g.radius),m.visible=g!==null}const h=c.joints["index-finger-tip"],u=c.joints["thumb-tip"],f=h.position.distanceTo(u.position),p=.02,_=.005;c.inputState.pinching&&f>p+_?(c.inputState.pinching=!1,this.dispatchEvent({type:"pinchend",handedness:e.handedness,target:this})):!c.inputState.pinching&&f<=p-_&&(c.inputState.pinching=!0,this.dispatchEvent({type:"pinchstart",handedness:e.handedness,target:this}))}else l!==null&&e.gripSpace&&(s=t.getPose(e.gripSpace,n),s!==null&&(l.matrix.fromArray(s.transform.matrix),l.matrix.decompose(l.position,l.rotation,l.scale),l.matrixWorldNeedsUpdate=!0,s.linearVelocity?(l.hasLinearVelocity=!0,l.linearVelocity.copy(s.linearVelocity)):l.hasLinearVelocity=!1,s.angularVelocity?(l.hasAngularVelocity=!0,l.angularVelocity.copy(s.angularVelocity)):l.hasAngularVelocity=!1));o!==null&&(r=t.getPose(e.targetRaySpace,n),r===null&&s!==null&&(r=s),r!==null&&(o.matrix.fromArray(r.transform.matrix),o.matrix.decompose(o.position,o.rotation,o.scale),o.matrixWorldNeedsUpdate=!0,r.linearVelocity?(o.hasLinearVelocity=!0,o.linearVelocity.copy(r.linearVelocity)):o.hasLinearVelocity=!1,r.angularVelocity?(o.hasAngularVelocity=!0,o.angularVelocity.copy(r.angularVelocity)):o.hasAngularVelocity=!1,this.dispatchEvent(Np)))}return o!==null&&(o.visible=r!==null),l!==null&&(l.visible=s!==null),c!==null&&(c.visible=a!==null),this}_getHandJoint(e,t){if(e.joints[t.jointName]===void 0){const n=new At;n.matrixAutoUpdate=!1,n.visible=!1,e.joints[t.jointName]=n,e.add(n)}return e.joints[t.jointName]}}class ic{constructor(e,t=25e-5){this.isFogExp2=!0,this.name="",this.color=new Ee(e),this.density=t}clone(){return new ic(this.color,this.density)}toJSON(){return{type:"FogExp2",name:this.name,color:this.color.getHex(),density:this.density}}}class qu extends pt{constructor(){super(),this.isScene=!0,this.type="Scene",this.background=null,this.environment=null,this.fog=null,this.backgroundBlurriness=0,this.backgroundIntensity=1,this.backgroundRotation=new pn,this.environmentIntensity=1,this.environmentRotation=new pn,this.overrideMaterial=null,typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}copy(e,t){return super.copy(e,t),e.background!==null&&(this.background=e.background.clone()),e.environment!==null&&(this.environment=e.environment.clone()),e.fog!==null&&(this.fog=e.fog.clone()),this.backgroundBlurriness=e.backgroundBlurriness,this.backgroundIntensity=e.backgroundIntensity,this.backgroundRotation.copy(e.backgroundRotation),this.environmentIntensity=e.environmentIntensity,this.environmentRotation.copy(e.environmentRotation),e.overrideMaterial!==null&&(this.overrideMaterial=e.overrideMaterial.clone()),this.matrixAutoUpdate=e.matrixAutoUpdate,this}toJSON(e){const t=super.toJSON(e);return this.fog!==null&&(t.object.fog=this.fog.toJSON()),this.backgroundBlurriness>0&&(t.object.backgroundBlurriness=this.backgroundBlurriness),this.backgroundIntensity!==1&&(t.object.backgroundIntensity=this.backgroundIntensity),t.object.backgroundRotation=this.backgroundRotation.toArray(),this.environmentIntensity!==1&&(t.object.environmentIntensity=this.environmentIntensity),t.object.environmentRotation=this.environmentRotation.toArray(),t}}class Yu{constructor(e,t){this.isInterleavedBuffer=!0,this.array=e,this.stride=t,this.count=e!==void 0?e.length/t:0,this.usage=Cl,this.updateRanges=[],this.version=0,this.uuid=bn()}onUploadCallback(){}set needsUpdate(e){e===!0&&this.version++}setUsage(e){return this.usage=e,this}addUpdateRange(e,t){this.updateRanges.push({start:e,count:t})}clearUpdateRanges(){this.updateRanges.length=0}copy(e){return this.array=new e.array.constructor(e.array),this.count=e.count,this.stride=e.stride,this.usage=e.usage,this}copyAt(e,t,n){e*=this.stride,n*=t.stride;for(let r=0,s=this.stride;r<s;r++)this.array[e+r]=t.array[n+r];return this}set(e,t=0){return this.array.set(e,t),this}clone(e){e.arrayBuffers===void 0&&(e.arrayBuffers={}),this.array.buffer._uuid===void 0&&(this.array.buffer._uuid=bn()),e.arrayBuffers[this.array.buffer._uuid]===void 0&&(e.arrayBuffers[this.array.buffer._uuid]=this.array.slice(0).buffer);const t=new this.array.constructor(e.arrayBuffers[this.array.buffer._uuid]),n=new this.constructor(t,this.stride);return n.setUsage(this.usage),n}onUpload(e){return this.onUploadCallback=e,this}toJSON(e){return e.arrayBuffers===void 0&&(e.arrayBuffers={}),this.array.buffer._uuid===void 0&&(this.array.buffer._uuid=bn()),e.arrayBuffers[this.array.buffer._uuid]===void 0&&(e.arrayBuffers[this.array.buffer._uuid]=Array.from(new Uint32Array(this.array.buffer))),{uuid:this.uuid,buffer:this.array.buffer._uuid,type:this.array.constructor.name,stride:this.stride}}}const Gt=new P;class xs{constructor(e,t,n,r=!1){this.isInterleavedBufferAttribute=!0,this.name="",this.data=e,this.itemSize=t,this.offset=n,this.normalized=r}get count(){return this.data.count}get array(){return this.data.array}set needsUpdate(e){this.data.needsUpdate=e}applyMatrix4(e){for(let t=0,n=this.data.count;t<n;t++)Gt.fromBufferAttribute(this,t),Gt.applyMatrix4(e),this.setXYZ(t,Gt.x,Gt.y,Gt.z);return this}applyNormalMatrix(e){for(let t=0,n=this.count;t<n;t++)Gt.fromBufferAttribute(this,t),Gt.applyNormalMatrix(e),this.setXYZ(t,Gt.x,Gt.y,Gt.z);return this}transformDirection(e){for(let t=0,n=this.count;t<n;t++)Gt.fromBufferAttribute(this,t),Gt.transformDirection(e),this.setXYZ(t,Gt.x,Gt.y,Gt.z);return this}getComponent(e,t){let n=this.array[e*this.data.stride+this.offset+t];return this.normalized&&(n=vn(n,this.array)),n}setComponent(e,t,n){return this.normalized&&(n=st(n,this.array)),this.data.array[e*this.data.stride+this.offset+t]=n,this}setX(e,t){return this.normalized&&(t=st(t,this.array)),this.data.array[e*this.data.stride+this.offset]=t,this}setY(e,t){return this.normalized&&(t=st(t,this.array)),this.data.array[e*this.data.stride+this.offset+1]=t,this}setZ(e,t){return this.normalized&&(t=st(t,this.array)),this.data.array[e*this.data.stride+this.offset+2]=t,this}setW(e,t){return this.normalized&&(t=st(t,this.array)),this.data.array[e*this.data.stride+this.offset+3]=t,this}getX(e){let t=this.data.array[e*this.data.stride+this.offset];return this.normalized&&(t=vn(t,this.array)),t}getY(e){let t=this.data.array[e*this.data.stride+this.offset+1];return this.normalized&&(t=vn(t,this.array)),t}getZ(e){let t=this.data.array[e*this.data.stride+this.offset+2];return this.normalized&&(t=vn(t,this.array)),t}getW(e){let t=this.data.array[e*this.data.stride+this.offset+3];return this.normalized&&(t=vn(t,this.array)),t}setXY(e,t,n){return e=e*this.data.stride+this.offset,this.normalized&&(t=st(t,this.array),n=st(n,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this}setXYZ(e,t,n,r){return e=e*this.data.stride+this.offset,this.normalized&&(t=st(t,this.array),n=st(n,this.array),r=st(r,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this.data.array[e+2]=r,this}setXYZW(e,t,n,r,s){return e=e*this.data.stride+this.offset,this.normalized&&(t=st(t,this.array),n=st(n,this.array),r=st(r,this.array),s=st(s,this.array)),this.data.array[e+0]=t,this.data.array[e+1]=n,this.data.array[e+2]=r,this.data.array[e+3]=s,this}clone(e){if(e===void 0){console.log("THREE.InterleavedBufferAttribute.clone(): Cloning an interleaved buffer attribute will de-interleave buffer data.");const t=[];for(let n=0;n<this.count;n++){const r=n*this.data.stride+this.offset;for(let s=0;s<this.itemSize;s++)t.push(this.data.array[r+s])}return new Ot(new this.array.constructor(t),this.itemSize,this.normalized)}else return e.interleavedBuffers===void 0&&(e.interleavedBuffers={}),e.interleavedBuffers[this.data.uuid]===void 0&&(e.interleavedBuffers[this.data.uuid]=this.data.clone(e)),new xs(e.interleavedBuffers[this.data.uuid],this.itemSize,this.offset,this.normalized)}toJSON(e){if(e===void 0){console.log("THREE.InterleavedBufferAttribute.toJSON(): Serializing an interleaved buffer attribute will de-interleave buffer data.");const t=[];for(let n=0;n<this.count;n++){const r=n*this.data.stride+this.offset;for(let s=0;s<this.itemSize;s++)t.push(this.data.array[r+s])}return{itemSize:this.itemSize,type:this.array.constructor.name,array:t,normalized:this.normalized}}else return e.interleavedBuffers===void 0&&(e.interleavedBuffers={}),e.interleavedBuffers[this.data.uuid]===void 0&&(e.interleavedBuffers[this.data.uuid]=this.data.toJSON(e)),{isInterleavedBufferAttribute:!0,itemSize:this.itemSize,data:this.data.uuid,offset:this.offset,normalized:this.normalized}}}class Ku extends hn{constructor(e){super(),this.isSpriteMaterial=!0,this.type="SpriteMaterial",this.color=new Ee(16777215),this.map=null,this.alphaMap=null,this.rotation=0,this.sizeAttenuation=!0,this.transparent=!0,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.alphaMap=e.alphaMap,this.rotation=e.rotation,this.sizeAttenuation=e.sizeAttenuation,this.fog=e.fog,this}}let er;const qr=new P,tr=new P,nr=new P,ir=new xe,Yr=new xe,$u=new De,ea=new P,Kr=new P,ta=new P,fd=new xe,Eo=new xe,pd=new xe;class Up extends pt{constructor(e=new Ku){if(super(),this.isSprite=!0,this.type="Sprite",er===void 0){er=new yt;const t=new Float32Array([-.5,-.5,0,0,0,.5,-.5,0,1,0,.5,.5,0,1,1,-.5,.5,0,0,1]),n=new Yu(t,5);er.setIndex([0,1,2,0,2,3]),er.setAttribute("position",new xs(n,3,0,!1)),er.setAttribute("uv",new xs(n,2,3,!1))}this.geometry=er,this.material=e,this.center=new xe(.5,.5),this.count=1}raycast(e,t){e.camera===null&&console.error('THREE.Sprite: "Raycaster.camera" needs to be set in order to raycast against sprites.'),tr.setFromMatrixScale(this.matrixWorld),$u.copy(e.camera.matrixWorld),this.modelViewMatrix.multiplyMatrices(e.camera.matrixWorldInverse,this.matrixWorld),nr.setFromMatrixPosition(this.modelViewMatrix),e.camera.isPerspectiveCamera&&this.material.sizeAttenuation===!1&&tr.multiplyScalar(-nr.z);const n=this.material.rotation;let r,s;n!==0&&(s=Math.cos(n),r=Math.sin(n));const a=this.center;na(ea.set(-.5,-.5,0),nr,a,tr,r,s),na(Kr.set(.5,-.5,0),nr,a,tr,r,s),na(ta.set(.5,.5,0),nr,a,tr,r,s),fd.set(0,0),Eo.set(1,0),pd.set(1,1);let o=e.ray.intersectTriangle(ea,Kr,ta,!1,qr);if(o===null&&(na(Kr.set(-.5,.5,0),nr,a,tr,r,s),Eo.set(0,1),o=e.ray.intersectTriangle(ea,ta,Kr,!1,qr),o===null))return;const l=e.ray.origin.distanceTo(qr);l<e.near||l>e.far||t.push({distance:l,point:qr.clone(),uv:rn.getInterpolation(qr,ea,Kr,ta,fd,Eo,pd,new xe),face:null,object:this})}copy(e,t){return super.copy(e,t),e.center!==void 0&&this.center.copy(e.center),this.material=e.material,this}}function na(i,e,t,n,r,s){ir.subVectors(i,t).addScalar(.5).multiply(n),r!==void 0?(Yr.x=s*ir.x-r*ir.y,Yr.y=r*ir.x+s*ir.y):Yr.copy(ir),i.copy(e),i.x+=Yr.x,i.y+=Yr.y,i.applyMatrix4($u)}const md=new P,gd=new Ye,_d=new Ye,Fp=new P,yd=new De,ia=new P,To=new Un,xd=new De,Ao=new Fr;class Op extends ut{constructor(e,t){super(e,t),this.isSkinnedMesh=!0,this.type="SkinnedMesh",this.bindMode=Vc,this.bindMatrix=new De,this.bindMatrixInverse=new De,this.boundingBox=null,this.boundingSphere=null}computeBoundingBox(){const e=this.geometry;this.boundingBox===null&&(this.boundingBox=new kt),this.boundingBox.makeEmpty();const t=e.getAttribute("position");for(let n=0;n<t.count;n++)this.getVertexPosition(n,ia),this.boundingBox.expandByPoint(ia)}computeBoundingSphere(){const e=this.geometry;this.boundingSphere===null&&(this.boundingSphere=new Un),this.boundingSphere.makeEmpty();const t=e.getAttribute("position");for(let n=0;n<t.count;n++)this.getVertexPosition(n,ia),this.boundingSphere.expandByPoint(ia)}copy(e,t){return super.copy(e,t),this.bindMode=e.bindMode,this.bindMatrix.copy(e.bindMatrix),this.bindMatrixInverse.copy(e.bindMatrixInverse),this.skeleton=e.skeleton,e.boundingBox!==null&&(this.boundingBox=e.boundingBox.clone()),e.boundingSphere!==null&&(this.boundingSphere=e.boundingSphere.clone()),this}raycast(e,t){const n=this.material,r=this.matrixWorld;n!==void 0&&(this.boundingSphere===null&&this.computeBoundingSphere(),To.copy(this.boundingSphere),To.applyMatrix4(r),e.ray.intersectsSphere(To)!==!1&&(xd.copy(r).invert(),Ao.copy(e.ray).applyMatrix4(xd),!(this.boundingBox!==null&&Ao.intersectsBox(this.boundingBox)===!1)&&this._computeIntersections(e,t,Ao)))}getVertexPosition(e,t){return super.getVertexPosition(e,t),this.applyBoneTransform(e,t),t}bind(e,t){this.skeleton=e,t===void 0&&(this.updateMatrixWorld(!0),this.skeleton.calculateInverses(),t=this.matrixWorld),this.bindMatrix.copy(t),this.bindMatrixInverse.copy(t).invert()}pose(){this.skeleton.pose()}normalizeSkinWeights(){const e=new Ye,t=this.geometry.attributes.skinWeight;for(let n=0,r=t.count;n<r;n++){e.fromBufferAttribute(t,n);const s=1/e.manhattanLength();s!==1/0?e.multiplyScalar(s):e.set(1,0,0,0),t.setXYZW(n,e.x,e.y,e.z,e.w)}}updateMatrixWorld(e){super.updateMatrixWorld(e),this.bindMode===Vc?this.bindMatrixInverse.copy(this.matrixWorld).invert():this.bindMode===If?this.bindMatrixInverse.copy(this.bindMatrix).invert():console.warn("THREE.SkinnedMesh: Unrecognized bindMode: "+this.bindMode)}applyBoneTransform(e,t){const n=this.skeleton,r=this.geometry;gd.fromBufferAttribute(r.attributes.skinIndex,e),_d.fromBufferAttribute(r.attributes.skinWeight,e),md.copy(t).applyMatrix4(this.bindMatrix),t.set(0,0,0);for(let s=0;s<4;s++){const a=_d.getComponent(s);if(a!==0){const o=gd.getComponent(s);yd.multiplyMatrices(n.bones[o].matrixWorld,n.boneInverses[o]),t.addScaledVector(Fp.copy(md).applyMatrix4(yd),a)}}return t.applyMatrix4(this.bindMatrixInverse)}}class Zu extends pt{constructor(){super(),this.isBone=!0,this.type="Bone"}}class Wa extends Ct{constructor(e=null,t=1,n=1,r,s,a,o,l,c=qt,h=qt,u,f){super(null,a,o,l,c,h,r,s,u,f),this.isDataTexture=!0,this.image={data:e,width:t,height:n},this.generateMipmaps=!1,this.flipY=!1,this.unpackAlignment=1}}const vd=new De,Bp=new De;class rc{constructor(e=[],t=[]){this.uuid=bn(),this.bones=e.slice(0),this.boneInverses=t,this.boneMatrices=null,this.boneTexture=null,this.init()}init(){const e=this.bones,t=this.boneInverses;if(this.boneMatrices=new Float32Array(e.length*16),t.length===0)this.calculateInverses();else if(e.length!==t.length){console.warn("THREE.Skeleton: Number of inverse bone matrices does not match amount of bones."),this.boneInverses=[];for(let n=0,r=this.bones.length;n<r;n++)this.boneInverses.push(new De)}}calculateInverses(){this.boneInverses.length=0;for(let e=0,t=this.bones.length;e<t;e++){const n=new De;this.bones[e]&&n.copy(this.bones[e].matrixWorld).invert(),this.boneInverses.push(n)}}pose(){for(let e=0,t=this.bones.length;e<t;e++){const n=this.bones[e];n&&n.matrixWorld.copy(this.boneInverses[e]).invert()}for(let e=0,t=this.bones.length;e<t;e++){const n=this.bones[e];n&&(n.parent&&n.parent.isBone?(n.matrix.copy(n.parent.matrixWorld).invert(),n.matrix.multiply(n.matrixWorld)):n.matrix.copy(n.matrixWorld),n.matrix.decompose(n.position,n.quaternion,n.scale))}}update(){const e=this.bones,t=this.boneInverses,n=this.boneMatrices,r=this.boneTexture;for(let s=0,a=e.length;s<a;s++){const o=e[s]?e[s].matrixWorld:Bp;vd.multiplyMatrices(o,t[s]),vd.toArray(n,s*16)}r!==null&&(r.needsUpdate=!0)}clone(){return new rc(this.bones,this.boneInverses)}computeBoneTexture(){let e=Math.sqrt(this.bones.length*4);e=Math.ceil(e/4)*4,e=Math.max(e,4);const t=new Float32Array(e*e*4);t.set(this.boneMatrices);const n=new Wa(t,e,e,sn,$t);return n.needsUpdate=!0,this.boneMatrices=t,this.boneTexture=n,this}getBoneByName(e){for(let t=0,n=this.bones.length;t<n;t++){const r=this.bones[t];if(r.name===e)return r}}dispose(){this.boneTexture!==null&&(this.boneTexture.dispose(),this.boneTexture=null)}fromJSON(e,t){this.uuid=e.uuid;for(let n=0,r=e.bones.length;n<r;n++){const s=e.bones[n];let a=t[s];a===void 0&&(console.warn("THREE.Skeleton: No bone found with UUID:",s),a=new Zu),this.bones.push(a),this.boneInverses.push(new De().fromArray(e.boneInverses[n]))}return this.init(),this}toJSON(){const e={metadata:{version:4.7,type:"Skeleton",generator:"Skeleton.toJSON"},bones:[],boneInverses:[]};e.uuid=this.uuid;const t=this.bones,n=this.boneInverses;for(let r=0,s=t.length;r<s;r++){const a=t[r];e.bones.push(a.uuid);const o=n[r];e.boneInverses.push(o.toArray())}return e}}class Pl extends Ot{constructor(e,t,n,r=1){super(e,t,n),this.isInstancedBufferAttribute=!0,this.meshPerAttribute=r}copy(e){return super.copy(e),this.meshPerAttribute=e.meshPerAttribute,this}toJSON(){const e=super.toJSON();return e.meshPerAttribute=this.meshPerAttribute,e.isInstancedBufferAttribute=!0,e}}const rr=new De,Md=new De,ra=[],bd=new kt,zp=new De,$r=new ut,Zr=new Un;class bs extends ut{constructor(e,t,n){super(e,t),this.isInstancedMesh=!0,this.instanceMatrix=new Pl(new Float32Array(n*16),16),this.instanceColor=null,this.morphTexture=null,this.count=n,this.boundingBox=null,this.boundingSphere=null;for(let r=0;r<n;r++)this.setMatrixAt(r,zp)}computeBoundingBox(){const e=this.geometry,t=this.count;this.boundingBox===null&&(this.boundingBox=new kt),e.boundingBox===null&&e.computeBoundingBox(),this.boundingBox.makeEmpty();for(let n=0;n<t;n++)this.getMatrixAt(n,rr),bd.copy(e.boundingBox).applyMatrix4(rr),this.boundingBox.union(bd)}computeBoundingSphere(){const e=this.geometry,t=this.count;this.boundingSphere===null&&(this.boundingSphere=new Un),e.boundingSphere===null&&e.computeBoundingSphere(),this.boundingSphere.makeEmpty();for(let n=0;n<t;n++)this.getMatrixAt(n,rr),Zr.copy(e.boundingSphere).applyMatrix4(rr),this.boundingSphere.union(Zr)}copy(e,t){return super.copy(e,t),this.instanceMatrix.copy(e.instanceMatrix),e.morphTexture!==null&&(this.morphTexture=e.morphTexture.clone()),e.instanceColor!==null&&(this.instanceColor=e.instanceColor.clone()),this.count=e.count,e.boundingBox!==null&&(this.boundingBox=e.boundingBox.clone()),e.boundingSphere!==null&&(this.boundingSphere=e.boundingSphere.clone()),this}getColorAt(e,t){t.fromArray(this.instanceColor.array,e*3)}getMatrixAt(e,t){t.fromArray(this.instanceMatrix.array,e*16)}getMorphAt(e,t){const n=t.morphTargetInfluences,r=this.morphTexture.source.data.data,s=n.length+1,a=e*s+1;for(let o=0;o<n.length;o++)n[o]=r[a+o]}raycast(e,t){const n=this.matrixWorld,r=this.count;if($r.geometry=this.geometry,$r.material=this.material,$r.material!==void 0&&(this.boundingSphere===null&&this.computeBoundingSphere(),Zr.copy(this.boundingSphere),Zr.applyMatrix4(n),e.ray.intersectsSphere(Zr)!==!1))for(let s=0;s<r;s++){this.getMatrixAt(s,rr),Md.multiplyMatrices(n,rr),$r.matrixWorld=Md,$r.raycast(e,ra);for(let a=0,o=ra.length;a<o;a++){const l=ra[a];l.instanceId=s,l.object=this,t.push(l)}ra.length=0}}setColorAt(e,t){this.instanceColor===null&&(this.instanceColor=new Pl(new Float32Array(this.instanceMatrix.count*3).fill(1),3)),t.toArray(this.instanceColor.array,e*3)}setMatrixAt(e,t){t.toArray(this.instanceMatrix.array,e*16)}setMorphAt(e,t){const n=t.morphTargetInfluences,r=n.length+1;this.morphTexture===null&&(this.morphTexture=new Wa(new Float32Array(r*this.count),r,this.count,Kl,$t));const s=this.morphTexture.source.data.data;let a=0;for(let c=0;c<n.length;c++)a+=n[c];const o=this.geometry.morphTargetsRelative?1:1-a,l=r*e;s[l]=o,s.set(n,l+1)}updateMorphTargets(){}dispose(){this.dispatchEvent({type:"dispose"}),this.morphTexture!==null&&(this.morphTexture.dispose(),this.morphTexture=null)}}const Ro=new P,kp=new P,Hp=new Ve;class jn{constructor(e=new P(1,0,0),t=0){this.isPlane=!0,this.normal=e,this.constant=t}set(e,t){return this.normal.copy(e),this.constant=t,this}setComponents(e,t,n,r){return this.normal.set(e,t,n),this.constant=r,this}setFromNormalAndCoplanarPoint(e,t){return this.normal.copy(e),this.constant=-t.dot(this.normal),this}setFromCoplanarPoints(e,t,n){const r=Ro.subVectors(n,t).cross(kp.subVectors(e,t)).normalize();return this.setFromNormalAndCoplanarPoint(r,e),this}copy(e){return this.normal.copy(e.normal),this.constant=e.constant,this}normalize(){const e=1/this.normal.length();return this.normal.multiplyScalar(e),this.constant*=e,this}negate(){return this.constant*=-1,this.normal.negate(),this}distanceToPoint(e){return this.normal.dot(e)+this.constant}distanceToSphere(e){return this.distanceToPoint(e.center)-e.radius}projectPoint(e,t){return t.copy(e).addScaledVector(this.normal,-this.distanceToPoint(e))}intersectLine(e,t){const n=e.delta(Ro),r=this.normal.dot(n);if(r===0)return this.distanceToPoint(e.start)===0?t.copy(e.start):null;const s=-(e.start.dot(this.normal)+this.constant)/r;return s<0||s>1?null:t.copy(e.start).addScaledVector(n,s)}intersectsLine(e){const t=this.distanceToPoint(e.start),n=this.distanceToPoint(e.end);return t<0&&n>0||n<0&&t>0}intersectsBox(e){return e.intersectsPlane(this)}intersectsSphere(e){return e.intersectsPlane(this)}coplanarPoint(e){return e.copy(this.normal).multiplyScalar(-this.constant)}applyMatrix4(e,t){const n=t||Hp.getNormalMatrix(e),r=this.coplanarPoint(Ro).applyMatrix4(e),s=this.normal.applyMatrix3(n).normalize();return this.constant=-r.dot(s),this}translate(e){return this.constant-=e.dot(this.normal),this}equals(e){return e.normal.equals(this.normal)&&e.constant===this.constant}clone(){return new this.constructor().copy(this)}}const wi=new Un,Gp=new xe(.5,.5),sa=new P;class Xa{constructor(e=new jn,t=new jn,n=new jn,r=new jn,s=new jn,a=new jn){this.planes=[e,t,n,r,s,a]}set(e,t,n,r,s,a){const o=this.planes;return o[0].copy(e),o[1].copy(t),o[2].copy(n),o[3].copy(r),o[4].copy(s),o[5].copy(a),this}copy(e){const t=this.planes;for(let n=0;n<6;n++)t[n].copy(e.planes[n]);return this}setFromProjectionMatrix(e,t=Ln,n=!1){const r=this.planes,s=e.elements,a=s[0],o=s[1],l=s[2],c=s[3],h=s[4],u=s[5],f=s[6],p=s[7],_=s[8],y=s[9],g=s[10],m=s[11],E=s[12],w=s[13],x=s[14],T=s[15];if(r[0].setComponents(c-a,p-h,m-_,T-E).normalize(),r[1].setComponents(c+a,p+h,m+_,T+E).normalize(),r[2].setComponents(c+o,p+u,m+y,T+w).normalize(),r[3].setComponents(c-o,p-u,m-y,T-w).normalize(),n)r[4].setComponents(l,f,g,x).normalize(),r[5].setComponents(c-l,p-f,m-g,T-x).normalize();else if(r[4].setComponents(c-l,p-f,m-g,T-x).normalize(),t===Ln)r[5].setComponents(c+l,p+f,m+g,T+x).normalize();else if(t===Ua)r[5].setComponents(l,f,g,x).normalize();else throw new Error("THREE.Frustum.setFromProjectionMatrix(): Invalid coordinate system: "+t);return this}intersectsObject(e){if(e.boundingSphere!==void 0)e.boundingSphere===null&&e.computeBoundingSphere(),wi.copy(e.boundingSphere).applyMatrix4(e.matrixWorld);else{const t=e.geometry;t.boundingSphere===null&&t.computeBoundingSphere(),wi.copy(t.boundingSphere).applyMatrix4(e.matrixWorld)}return this.intersectsSphere(wi)}intersectsSprite(e){wi.center.set(0,0,0);const t=Gp.distanceTo(e.center);return wi.radius=.7071067811865476+t,wi.applyMatrix4(e.matrixWorld),this.intersectsSphere(wi)}intersectsSphere(e){const t=this.planes,n=e.center,r=-e.radius;for(let s=0;s<6;s++)if(t[s].distanceToPoint(n)<r)return!1;return!0}intersectsBox(e){const t=this.planes;for(let n=0;n<6;n++){const r=t[n];if(sa.x=r.normal.x>0?e.max.x:e.min.x,sa.y=r.normal.y>0?e.max.y:e.min.y,sa.z=r.normal.z>0?e.max.z:e.min.z,r.distanceToPoint(sa)<0)return!1}return!0}containsPoint(e){const t=this.planes;for(let n=0;n<6;n++)if(t[n].distanceToPoint(e)<0)return!1;return!0}clone(){return new this.constructor().copy(this)}}class Fn extends hn{constructor(e){super(),this.isLineBasicMaterial=!0,this.type="LineBasicMaterial",this.color=new Ee(16777215),this.map=null,this.linewidth=1,this.linecap="round",this.linejoin="round",this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.linewidth=e.linewidth,this.linecap=e.linecap,this.linejoin=e.linejoin,this.fog=e.fog,this}}const Fa=new P,Oa=new P,Sd=new De,Jr=new Fr,aa=new Un,Co=new P,wd=new P;class sc extends pt{constructor(e=new yt,t=new Fn){super(),this.isLine=!0,this.type="Line",this.geometry=e,this.material=t,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}computeLineDistances(){const e=this.geometry;if(e.index===null){const t=e.attributes.position,n=[0];for(let r=1,s=t.count;r<s;r++)Fa.fromBufferAttribute(t,r-1),Oa.fromBufferAttribute(t,r),n[r]=n[r-1],n[r]+=Fa.distanceTo(Oa);e.setAttribute("lineDistance",new mt(n,1))}else console.warn("THREE.Line.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.");return this}raycast(e,t){const n=this.geometry,r=this.matrixWorld,s=e.params.Line.threshold,a=n.drawRange;if(n.boundingSphere===null&&n.computeBoundingSphere(),aa.copy(n.boundingSphere),aa.applyMatrix4(r),aa.radius+=s,e.ray.intersectsSphere(aa)===!1)return;Sd.copy(r).invert(),Jr.copy(e.ray).applyMatrix4(Sd);const o=s/((this.scale.x+this.scale.y+this.scale.z)/3),l=o*o,c=this.isLineSegments?2:1,h=n.index,f=n.attributes.position;if(h!==null){const p=Math.max(0,a.start),_=Math.min(h.count,a.start+a.count);for(let y=p,g=_-1;y<g;y+=c){const m=h.getX(y),E=h.getX(y+1),w=oa(this,e,Jr,l,m,E,y);w&&t.push(w)}if(this.isLineLoop){const y=h.getX(_-1),g=h.getX(p),m=oa(this,e,Jr,l,y,g,_-1);m&&t.push(m)}}else{const p=Math.max(0,a.start),_=Math.min(f.count,a.start+a.count);for(let y=p,g=_-1;y<g;y+=c){const m=oa(this,e,Jr,l,y,y+1,y);m&&t.push(m)}if(this.isLineLoop){const y=oa(this,e,Jr,l,_-1,p,_-1);y&&t.push(y)}}}updateMorphTargets(){const t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){const r=t[n[0]];if(r!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let s=0,a=r.length;s<a;s++){const o=r[s].name||String(s);this.morphTargetInfluences.push(0),this.morphTargetDictionary[o]=s}}}}}function oa(i,e,t,n,r,s,a){const o=i.geometry.attributes.position;if(Fa.fromBufferAttribute(o,r),Oa.fromBufferAttribute(o,s),t.distanceSqToSegment(Fa,Oa,Co,wd)>n)return;Co.applyMatrix4(i.matrixWorld);const c=e.ray.origin.distanceTo(Co);if(!(c<e.near||c>e.far))return{distance:c,point:wd.clone().applyMatrix4(i.matrixWorld),index:a,face:null,faceIndex:null,barycoord:null,object:i}}const Ed=new P,Td=new P;class ni extends sc{constructor(e,t){super(e,t),this.isLineSegments=!0,this.type="LineSegments"}computeLineDistances(){const e=this.geometry;if(e.index===null){const t=e.attributes.position,n=[];for(let r=0,s=t.count;r<s;r+=2)Ed.fromBufferAttribute(t,r),Td.fromBufferAttribute(t,r+1),n[r]=r===0?0:n[r-1],n[r+1]=n[r]+Ed.distanceTo(Td);e.setAttribute("lineDistance",new mt(n,1))}else console.warn("THREE.LineSegments.computeLineDistances(): Computation only possible with non-indexed BufferGeometry.");return this}}class Vp extends sc{constructor(e,t){super(e,t),this.isLineLoop=!0,this.type="LineLoop"}}class ac extends hn{constructor(e){super(),this.isPointsMaterial=!0,this.type="PointsMaterial",this.color=new Ee(16777215),this.map=null,this.alphaMap=null,this.size=1,this.sizeAttenuation=!0,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.alphaMap=e.alphaMap,this.size=e.size,this.sizeAttenuation=e.sizeAttenuation,this.fog=e.fog,this}}const Ad=new De,Il=new Fr,la=new Un,ca=new P;class Ju extends pt{constructor(e=new yt,t=new ac){super(),this.isPoints=!0,this.type="Points",this.geometry=e,this.material=t,this.morphTargetDictionary=void 0,this.morphTargetInfluences=void 0,this.updateMorphTargets()}copy(e,t){return super.copy(e,t),this.material=Array.isArray(e.material)?e.material.slice():e.material,this.geometry=e.geometry,this}raycast(e,t){const n=this.geometry,r=this.matrixWorld,s=e.params.Points.threshold,a=n.drawRange;if(n.boundingSphere===null&&n.computeBoundingSphere(),la.copy(n.boundingSphere),la.applyMatrix4(r),la.radius+=s,e.ray.intersectsSphere(la)===!1)return;Ad.copy(r).invert(),Il.copy(e.ray).applyMatrix4(Ad);const o=s/((this.scale.x+this.scale.y+this.scale.z)/3),l=o*o,c=n.index,u=n.attributes.position;if(c!==null){const f=Math.max(0,a.start),p=Math.min(c.count,a.start+a.count);for(let _=f,y=p;_<y;_++){const g=c.getX(_);ca.fromBufferAttribute(u,g),Rd(ca,g,l,r,e,t,this)}}else{const f=Math.max(0,a.start),p=Math.min(u.count,a.start+a.count);for(let _=f,y=p;_<y;_++)ca.fromBufferAttribute(u,_),Rd(ca,_,l,r,e,t,this)}}updateMorphTargets(){const t=this.geometry.morphAttributes,n=Object.keys(t);if(n.length>0){const r=t[n[0]];if(r!==void 0){this.morphTargetInfluences=[],this.morphTargetDictionary={};for(let s=0,a=r.length;s<a;s++){const o=r[s].name||String(s);this.morphTargetInfluences.push(0),this.morphTargetDictionary[o]=s}}}}}function Rd(i,e,t,n,r,s,a){const o=Il.distanceSqToPoint(i);if(o<t){const l=new P;Il.closestPointToPoint(i,l),l.applyMatrix4(n);const c=r.ray.origin.distanceTo(l);if(c<r.near||c>r.far)return;s.push({distance:c,distanceToRay:Math.sqrt(o),point:l,index:e,face:null,faceIndex:null,barycoord:null,object:a})}}class Wp extends Ct{constructor(e,t,n,r,s,a,o,l,c){super(e,t,n,r,s,a,o,l,c),this.isCanvasTexture=!0,this.needsUpdate=!0}}class Qu extends Ct{constructor(e,t,n=Di,r,s,a,o=qt,l=qt,c,h=ps,u=1){if(h!==ps&&h!==ms)throw new Error("DepthTexture format must be either THREE.DepthFormat or THREE.DepthStencilFormat");const f={width:e,height:t,depth:u};super(f,r,s,a,o,l,h,n,c),this.isDepthTexture=!0,this.flipY=!1,this.generateMipmaps=!1,this.compareFunction=null}copy(e){return super.copy(e),this.source=new tc(Object.assign({},e.image)),this.compareFunction=e.compareFunction,this}toJSON(e){const t=super.toJSON(e);return this.compareFunction!==null&&(t.compareFunction=this.compareFunction),t}}class ja extends yt{constructor(e=1,t=1,n=1,r=32,s=1,a=!1,o=0,l=Math.PI*2){super(),this.type="CylinderGeometry",this.parameters={radiusTop:e,radiusBottom:t,height:n,radialSegments:r,heightSegments:s,openEnded:a,thetaStart:o,thetaLength:l};const c=this;r=Math.floor(r),s=Math.floor(s);const h=[],u=[],f=[],p=[];let _=0;const y=[],g=n/2;let m=0;E(),a===!1&&(e>0&&w(!0),t>0&&w(!1)),this.setIndex(h),this.setAttribute("position",new mt(u,3)),this.setAttribute("normal",new mt(f,3)),this.setAttribute("uv",new mt(p,2));function E(){const x=new P,T=new P;let L=0;const C=(t-e)/n;for(let R=0;R<=s;R++){const v=[],b=R/s,A=b*(t-e)+e;for(let U=0;U<=r;U++){const z=U/r,B=z*l+o,V=Math.sin(B),G=Math.cos(B);T.x=A*V,T.y=-b*n+g,T.z=A*G,u.push(T.x,T.y,T.z),x.set(V,C,G).normalize(),f.push(x.x,x.y,x.z),p.push(z,1-b),v.push(_++)}y.push(v)}for(let R=0;R<r;R++)for(let v=0;v<s;v++){const b=y[v][R],A=y[v+1][R],U=y[v+1][R+1],z=y[v][R+1];(e>0||v!==0)&&(h.push(b,A,z),L+=3),(t>0||v!==s-1)&&(h.push(A,U,z),L+=3)}c.addGroup(m,L,0),m+=L}function w(x){const T=_,L=new xe,C=new P;let R=0;const v=x===!0?e:t,b=x===!0?1:-1;for(let U=1;U<=r;U++)u.push(0,g*b,0),f.push(0,b,0),p.push(.5,.5),_++;const A=_;for(let U=0;U<=r;U++){const B=U/r*l+o,V=Math.cos(B),G=Math.sin(B);C.x=v*G,C.y=g*b,C.z=v*V,u.push(C.x,C.y,C.z),f.push(0,b,0),L.x=V*.5+.5,L.y=G*.5*b+.5,p.push(L.x,L.y),_++}for(let U=0;U<r;U++){const z=T+U,B=A+U;x===!0?h.push(B,B+1,z):h.push(B+1,B,z),R+=3}c.addGroup(m,R,x===!0?1:2),m+=R}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new ja(e.radiusTop,e.radiusBottom,e.height,e.radialSegments,e.heightSegments,e.openEnded,e.thetaStart,e.thetaLength)}}class oc extends yt{constructor(e=[],t=[],n=1,r=0){super(),this.type="PolyhedronGeometry",this.parameters={vertices:e,indices:t,radius:n,detail:r};const s=[],a=[];o(r),c(n),h(),this.setAttribute("position",new mt(s,3)),this.setAttribute("normal",new mt(s.slice(),3)),this.setAttribute("uv",new mt(a,2)),r===0?this.computeVertexNormals():this.normalizeNormals();function o(E){const w=new P,x=new P,T=new P;for(let L=0;L<t.length;L+=3)p(t[L+0],w),p(t[L+1],x),p(t[L+2],T),l(w,x,T,E)}function l(E,w,x,T){const L=T+1,C=[];for(let R=0;R<=L;R++){C[R]=[];const v=E.clone().lerp(x,R/L),b=w.clone().lerp(x,R/L),A=L-R;for(let U=0;U<=A;U++)U===0&&R===L?C[R][U]=v:C[R][U]=v.clone().lerp(b,U/A)}for(let R=0;R<L;R++)for(let v=0;v<2*(L-R)-1;v++){const b=Math.floor(v/2);v%2===0?(f(C[R][b+1]),f(C[R+1][b]),f(C[R][b])):(f(C[R][b+1]),f(C[R+1][b+1]),f(C[R+1][b]))}}function c(E){const w=new P;for(let x=0;x<s.length;x+=3)w.x=s[x+0],w.y=s[x+1],w.z=s[x+2],w.normalize().multiplyScalar(E),s[x+0]=w.x,s[x+1]=w.y,s[x+2]=w.z}function h(){const E=new P;for(let w=0;w<s.length;w+=3){E.x=s[w+0],E.y=s[w+1],E.z=s[w+2];const x=g(E)/2/Math.PI+.5,T=m(E)/Math.PI+.5;a.push(x,1-T)}_(),u()}function u(){for(let E=0;E<a.length;E+=6){const w=a[E+0],x=a[E+2],T=a[E+4],L=Math.max(w,x,T),C=Math.min(w,x,T);L>.9&&C<.1&&(w<.2&&(a[E+0]+=1),x<.2&&(a[E+2]+=1),T<.2&&(a[E+4]+=1))}}function f(E){s.push(E.x,E.y,E.z)}function p(E,w){const x=E*3;w.x=e[x+0],w.y=e[x+1],w.z=e[x+2]}function _(){const E=new P,w=new P,x=new P,T=new P,L=new xe,C=new xe,R=new xe;for(let v=0,b=0;v<s.length;v+=9,b+=6){E.set(s[v+0],s[v+1],s[v+2]),w.set(s[v+3],s[v+4],s[v+5]),x.set(s[v+6],s[v+7],s[v+8]),L.set(a[b+0],a[b+1]),C.set(a[b+2],a[b+3]),R.set(a[b+4],a[b+5]),T.copy(E).add(w).add(x).divideScalar(3);const A=g(T);y(L,b+0,E,A),y(C,b+2,w,A),y(R,b+4,x,A)}}function y(E,w,x,T){T<0&&E.x===1&&(a[w]=E.x-1),x.x===0&&x.z===0&&(a[w]=T/2/Math.PI+.5)}function g(E){return Math.atan2(E.z,-E.x)}function m(E){return Math.atan2(-E.y,Math.sqrt(E.x*E.x+E.z*E.z))}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new oc(e.vertices,e.indices,e.radius,e.details)}}const da=new P,ua=new P,Po=new P,ha=new rn;class eh extends yt{constructor(e=null,t=1){if(super(),this.type="EdgesGeometry",this.parameters={geometry:e,thresholdAngle:t},e!==null){const r=Math.pow(10,4),s=Math.cos(gr*t),a=e.getIndex(),o=e.getAttribute("position"),l=a?a.count:o.count,c=[0,0,0],h=["a","b","c"],u=new Array(3),f={},p=[];for(let _=0;_<l;_+=3){a?(c[0]=a.getX(_),c[1]=a.getX(_+1),c[2]=a.getX(_+2)):(c[0]=_,c[1]=_+1,c[2]=_+2);const{a:y,b:g,c:m}=ha;if(y.fromBufferAttribute(o,c[0]),g.fromBufferAttribute(o,c[1]),m.fromBufferAttribute(o,c[2]),ha.getNormal(Po),u[0]=`${Math.round(y.x*r)},${Math.round(y.y*r)},${Math.round(y.z*r)}`,u[1]=`${Math.round(g.x*r)},${Math.round(g.y*r)},${Math.round(g.z*r)}`,u[2]=`${Math.round(m.x*r)},${Math.round(m.y*r)},${Math.round(m.z*r)}`,!(u[0]===u[1]||u[1]===u[2]||u[2]===u[0]))for(let E=0;E<3;E++){const w=(E+1)%3,x=u[E],T=u[w],L=ha[h[E]],C=ha[h[w]],R=`${x}_${T}`,v=`${T}_${x}`;v in f&&f[v]?(Po.dot(f[v].normal)<=s&&(p.push(L.x,L.y,L.z),p.push(C.x,C.y,C.z)),f[v]=null):R in f||(f[R]={index0:c[E],index1:c[w],normal:Po.clone()})}}for(const _ in f)if(f[_]){const{index0:y,index1:g}=f[_];da.fromBufferAttribute(o,y),ua.fromBufferAttribute(o,g),p.push(da.x,da.y,da.z),p.push(ua.x,ua.y,ua.z)}this.setAttribute("position",new mt(p,3))}}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}}class lc extends oc{constructor(e=1,t=0){const n=(1+Math.sqrt(5))/2,r=[-1,n,0,1,n,0,-1,-n,0,1,-n,0,0,-1,n,0,1,n,0,-1,-n,0,1,-n,n,0,-1,n,0,1,-n,0,-1,-n,0,1],s=[0,11,5,0,5,1,0,1,7,0,7,10,0,10,11,1,5,9,5,11,4,11,10,2,10,7,6,7,1,8,3,9,4,3,4,2,3,2,6,3,6,8,3,8,9,4,9,5,2,4,11,6,2,10,8,6,7,9,8,1];super(r,s,e,t),this.type="IcosahedronGeometry",this.parameters={radius:e,detail:t}}static fromJSON(e){return new lc(e.radius,e.detail)}}class Ss extends yt{constructor(e=1,t=1,n=1,r=1){super(),this.type="PlaneGeometry",this.parameters={width:e,height:t,widthSegments:n,heightSegments:r};const s=e/2,a=t/2,o=Math.floor(n),l=Math.floor(r),c=o+1,h=l+1,u=e/o,f=t/l,p=[],_=[],y=[],g=[];for(let m=0;m<h;m++){const E=m*f-a;for(let w=0;w<c;w++){const x=w*u-s;_.push(x,-E,0),y.push(0,0,1),g.push(w/o),g.push(1-m/l)}}for(let m=0;m<l;m++)for(let E=0;E<o;E++){const w=E+c*m,x=E+c*(m+1),T=E+1+c*(m+1),L=E+1+c*m;p.push(w,x,L),p.push(x,T,L)}this.setIndex(p),this.setAttribute("position",new mt(_,3)),this.setAttribute("normal",new mt(y,3)),this.setAttribute("uv",new mt(g,2))}copy(e){return super.copy(e),this.parameters=Object.assign({},e.parameters),this}static fromJSON(e){return new Ss(e.width,e.height,e.widthSegments,e.heightSegments)}}class Dn extends hn{constructor(e){super(),this.isMeshStandardMaterial=!0,this.type="MeshStandardMaterial",this.defines={STANDARD:""},this.color=new Ee(16777215),this.roughness=1,this.metalness=0,this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new Ee(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=Ql,this.normalScale=new xe(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.roughnessMap=null,this.metalnessMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new pn,this.envMapIntensity=1,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.flatShading=!1,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.defines={STANDARD:""},this.color.copy(e.color),this.roughness=e.roughness,this.metalness=e.metalness,this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.emissive.copy(e.emissive),this.emissiveMap=e.emissiveMap,this.emissiveIntensity=e.emissiveIntensity,this.bumpMap=e.bumpMap,this.bumpScale=e.bumpScale,this.normalMap=e.normalMap,this.normalMapType=e.normalMapType,this.normalScale.copy(e.normalScale),this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.roughnessMap=e.roughnessMap,this.metalnessMap=e.metalnessMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.envMapIntensity=e.envMapIntensity,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.flatShading=e.flatShading,this.fog=e.fog,this}}class mn extends Dn{constructor(e){super(),this.isMeshPhysicalMaterial=!0,this.defines={STANDARD:"",PHYSICAL:""},this.type="MeshPhysicalMaterial",this.anisotropyRotation=0,this.anisotropyMap=null,this.clearcoatMap=null,this.clearcoatRoughness=0,this.clearcoatRoughnessMap=null,this.clearcoatNormalScale=new xe(1,1),this.clearcoatNormalMap=null,this.ior=1.5,Object.defineProperty(this,"reflectivity",{get:function(){return Xe(2.5*(this.ior-1)/(this.ior+1),0,1)},set:function(t){this.ior=(1+.4*t)/(1-.4*t)}}),this.iridescenceMap=null,this.iridescenceIOR=1.3,this.iridescenceThicknessRange=[100,400],this.iridescenceThicknessMap=null,this.sheenColor=new Ee(0),this.sheenColorMap=null,this.sheenRoughness=1,this.sheenRoughnessMap=null,this.transmissionMap=null,this.thickness=0,this.thicknessMap=null,this.attenuationDistance=1/0,this.attenuationColor=new Ee(1,1,1),this.specularIntensity=1,this.specularIntensityMap=null,this.specularColor=new Ee(1,1,1),this.specularColorMap=null,this._anisotropy=0,this._clearcoat=0,this._dispersion=0,this._iridescence=0,this._sheen=0,this._transmission=0,this.setValues(e)}get anisotropy(){return this._anisotropy}set anisotropy(e){this._anisotropy>0!=e>0&&this.version++,this._anisotropy=e}get clearcoat(){return this._clearcoat}set clearcoat(e){this._clearcoat>0!=e>0&&this.version++,this._clearcoat=e}get iridescence(){return this._iridescence}set iridescence(e){this._iridescence>0!=e>0&&this.version++,this._iridescence=e}get dispersion(){return this._dispersion}set dispersion(e){this._dispersion>0!=e>0&&this.version++,this._dispersion=e}get sheen(){return this._sheen}set sheen(e){this._sheen>0!=e>0&&this.version++,this._sheen=e}get transmission(){return this._transmission}set transmission(e){this._transmission>0!=e>0&&this.version++,this._transmission=e}copy(e){return super.copy(e),this.defines={STANDARD:"",PHYSICAL:""},this.anisotropy=e.anisotropy,this.anisotropyRotation=e.anisotropyRotation,this.anisotropyMap=e.anisotropyMap,this.clearcoat=e.clearcoat,this.clearcoatMap=e.clearcoatMap,this.clearcoatRoughness=e.clearcoatRoughness,this.clearcoatRoughnessMap=e.clearcoatRoughnessMap,this.clearcoatNormalMap=e.clearcoatNormalMap,this.clearcoatNormalScale.copy(e.clearcoatNormalScale),this.dispersion=e.dispersion,this.ior=e.ior,this.iridescence=e.iridescence,this.iridescenceMap=e.iridescenceMap,this.iridescenceIOR=e.iridescenceIOR,this.iridescenceThicknessRange=[...e.iridescenceThicknessRange],this.iridescenceThicknessMap=e.iridescenceThicknessMap,this.sheen=e.sheen,this.sheenColor.copy(e.sheenColor),this.sheenColorMap=e.sheenColorMap,this.sheenRoughness=e.sheenRoughness,this.sheenRoughnessMap=e.sheenRoughnessMap,this.transmission=e.transmission,this.transmissionMap=e.transmissionMap,this.thickness=e.thickness,this.thicknessMap=e.thicknessMap,this.attenuationDistance=e.attenuationDistance,this.attenuationColor.copy(e.attenuationColor),this.specularIntensity=e.specularIntensity,this.specularIntensityMap=e.specularIntensityMap,this.specularColor.copy(e.specularColor),this.specularColorMap=e.specularColorMap,this}}class Xp extends hn{constructor(e){super(),this.isMeshLambertMaterial=!0,this.type="MeshLambertMaterial",this.color=new Ee(16777215),this.map=null,this.lightMap=null,this.lightMapIntensity=1,this.aoMap=null,this.aoMapIntensity=1,this.emissive=new Ee(0),this.emissiveIntensity=1,this.emissiveMap=null,this.bumpMap=null,this.bumpScale=1,this.normalMap=null,this.normalMapType=Ql,this.normalScale=new xe(1,1),this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.specularMap=null,this.alphaMap=null,this.envMap=null,this.envMapRotation=new pn,this.combine=Xl,this.reflectivity=1,this.refractionRatio=.98,this.wireframe=!1,this.wireframeLinewidth=1,this.wireframeLinecap="round",this.wireframeLinejoin="round",this.flatShading=!1,this.fog=!0,this.setValues(e)}copy(e){return super.copy(e),this.color.copy(e.color),this.map=e.map,this.lightMap=e.lightMap,this.lightMapIntensity=e.lightMapIntensity,this.aoMap=e.aoMap,this.aoMapIntensity=e.aoMapIntensity,this.emissive.copy(e.emissive),this.emissiveMap=e.emissiveMap,this.emissiveIntensity=e.emissiveIntensity,this.bumpMap=e.bumpMap,this.bumpScale=e.bumpScale,this.normalMap=e.normalMap,this.normalMapType=e.normalMapType,this.normalScale.copy(e.normalScale),this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.specularMap=e.specularMap,this.alphaMap=e.alphaMap,this.envMap=e.envMap,this.envMapRotation.copy(e.envMapRotation),this.combine=e.combine,this.reflectivity=e.reflectivity,this.refractionRatio=e.refractionRatio,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this.wireframeLinecap=e.wireframeLinecap,this.wireframeLinejoin=e.wireframeLinejoin,this.flatShading=e.flatShading,this.fog=e.fog,this}}class jp extends hn{constructor(e){super(),this.isMeshDepthMaterial=!0,this.type="MeshDepthMaterial",this.depthPacking=Nf,this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.wireframe=!1,this.wireframeLinewidth=1,this.setValues(e)}copy(e){return super.copy(e),this.depthPacking=e.depthPacking,this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this.wireframe=e.wireframe,this.wireframeLinewidth=e.wireframeLinewidth,this}}class qp extends hn{constructor(e){super(),this.isMeshDistanceMaterial=!0,this.type="MeshDistanceMaterial",this.map=null,this.alphaMap=null,this.displacementMap=null,this.displacementScale=1,this.displacementBias=0,this.setValues(e)}copy(e){return super.copy(e),this.map=e.map,this.alphaMap=e.alphaMap,this.displacementMap=e.displacementMap,this.displacementScale=e.displacementScale,this.displacementBias=e.displacementBias,this}}class Yp extends Fn{constructor(e){super(),this.isLineDashedMaterial=!0,this.type="LineDashedMaterial",this.scale=1,this.dashSize=3,this.gapSize=1,this.setValues(e)}copy(e){return super.copy(e),this.scale=e.scale,this.dashSize=e.dashSize,this.gapSize=e.gapSize,this}}function fa(i,e){return!i||i.constructor===e?i:typeof e.BYTES_PER_ELEMENT=="number"?new e(i):Array.prototype.slice.call(i)}function Kp(i){return ArrayBuffer.isView(i)&&!(i instanceof DataView)}function $p(i){function e(r,s){return i[r]-i[s]}const t=i.length,n=new Array(t);for(let r=0;r!==t;++r)n[r]=r;return n.sort(e),n}function Cd(i,e,t){const n=i.length,r=new i.constructor(n);for(let s=0,a=0;a!==n;++s){const o=t[s]*e;for(let l=0;l!==e;++l)r[a++]=i[o+l]}return r}function th(i,e,t,n){let r=1,s=i[0];for(;s!==void 0&&s[n]===void 0;)s=i[r++];if(s===void 0)return;let a=s[n];if(a!==void 0)if(Array.isArray(a))do a=s[n],a!==void 0&&(e.push(s.time),t.push(...a)),s=i[r++];while(s!==void 0);else if(a.toArray!==void 0)do a=s[n],a!==void 0&&(e.push(s.time),a.toArray(t,t.length)),s=i[r++];while(s!==void 0);else do a=s[n],a!==void 0&&(e.push(s.time),t.push(a)),s=i[r++];while(s!==void 0)}class ws{constructor(e,t,n,r){this.parameterPositions=e,this._cachedIndex=0,this.resultBuffer=r!==void 0?r:new t.constructor(n),this.sampleValues=t,this.valueSize=n,this.settings=null,this.DefaultSettings_={}}evaluate(e){const t=this.parameterPositions;let n=this._cachedIndex,r=t[n],s=t[n-1];n:{e:{let a;t:{i:if(!(e<r)){for(let o=n+2;;){if(r===void 0){if(e<s)break i;return n=t.length,this._cachedIndex=n,this.copySampleValue_(n-1)}if(n===o)break;if(s=r,r=t[++n],e<r)break e}a=t.length;break t}if(!(e>=s)){const o=t[1];e<o&&(n=2,s=o);for(let l=n-2;;){if(s===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(n===l)break;if(r=s,s=t[--n-1],e>=s)break e}a=n,n=0;break t}break n}for(;n<a;){const o=n+a>>>1;e<t[o]?a=o:n=o+1}if(r=t[n],s=t[n-1],s===void 0)return this._cachedIndex=0,this.copySampleValue_(0);if(r===void 0)return n=t.length,this._cachedIndex=n,this.copySampleValue_(n-1)}this._cachedIndex=n,this.intervalChanged_(n,s,r)}return this.interpolate_(n,s,e,r)}getSettings_(){return this.settings||this.DefaultSettings_}copySampleValue_(e){const t=this.resultBuffer,n=this.sampleValues,r=this.valueSize,s=e*r;for(let a=0;a!==r;++a)t[a]=n[s+a];return t}interpolate_(){throw new Error("call to abstract method")}intervalChanged_(){}}class Zp extends ws{constructor(e,t,n,r){super(e,t,n,r),this._weightPrev=-0,this._offsetPrev=-0,this._weightNext=-0,this._offsetNext=-0,this.DefaultSettings_={endingStart:Wc,endingEnd:Wc}}intervalChanged_(e,t,n){const r=this.parameterPositions;let s=e-2,a=e+1,o=r[s],l=r[a];if(o===void 0)switch(this.getSettings_().endingStart){case Xc:s=e,o=2*t-n;break;case jc:s=r.length-2,o=t+r[s]-r[s+1];break;default:s=e,o=n}if(l===void 0)switch(this.getSettings_().endingEnd){case Xc:a=e,l=2*n-t;break;case jc:a=1,l=n+r[1]-r[0];break;default:a=e-1,l=t}const c=(n-t)*.5,h=this.valueSize;this._weightPrev=c/(t-o),this._weightNext=c/(l-n),this._offsetPrev=s*h,this._offsetNext=a*h}interpolate_(e,t,n,r){const s=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=e*o,c=l-o,h=this._offsetPrev,u=this._offsetNext,f=this._weightPrev,p=this._weightNext,_=(n-t)/(r-t),y=_*_,g=y*_,m=-f*g+2*f*y-f*_,E=(1+f)*g+(-1.5-2*f)*y+(-.5+f)*_+1,w=(-1-p)*g+(1.5+p)*y+.5*_,x=p*g-p*y;for(let T=0;T!==o;++T)s[T]=m*a[h+T]+E*a[c+T]+w*a[l+T]+x*a[u+T];return s}}class Jp extends ws{constructor(e,t,n,r){super(e,t,n,r)}interpolate_(e,t,n,r){const s=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=e*o,c=l-o,h=(n-t)/(r-t),u=1-h;for(let f=0;f!==o;++f)s[f]=a[c+f]*u+a[l+f]*h;return s}}class Qp extends ws{constructor(e,t,n,r){super(e,t,n,r)}interpolate_(e){return this.copySampleValue_(e-1)}}class Tn{constructor(e,t,n,r){if(e===void 0)throw new Error("THREE.KeyframeTrack: track name is undefined");if(t===void 0||t.length===0)throw new Error("THREE.KeyframeTrack: no keyframes in track named "+e);this.name=e,this.times=fa(t,this.TimeBufferType),this.values=fa(n,this.ValueBufferType),this.setInterpolation(r||this.DefaultInterpolation)}static toJSON(e){const t=e.constructor;let n;if(t.toJSON!==this.toJSON)n=t.toJSON(e);else{n={name:e.name,times:fa(e.times,Array),values:fa(e.values,Array)};const r=e.getInterpolation();r!==e.DefaultInterpolation&&(n.interpolation=r)}return n.type=e.ValueTypeName,n}InterpolantFactoryMethodDiscrete(e){return new Qp(this.times,this.values,this.getValueSize(),e)}InterpolantFactoryMethodLinear(e){return new Jp(this.times,this.values,this.getValueSize(),e)}InterpolantFactoryMethodSmooth(e){return new Zp(this.times,this.values,this.getValueSize(),e)}setInterpolation(e){let t;switch(e){case gs:t=this.InterpolantFactoryMethodDiscrete;break;case _s:t=this.InterpolantFactoryMethodLinear;break;case no:t=this.InterpolantFactoryMethodSmooth;break}if(t===void 0){const n="unsupported interpolation for "+this.ValueTypeName+" keyframe track named "+this.name;if(this.createInterpolant===void 0)if(e!==this.DefaultInterpolation)this.setInterpolation(this.DefaultInterpolation);else throw new Error(n);return console.warn("THREE.KeyframeTrack:",n),this}return this.createInterpolant=t,this}getInterpolation(){switch(this.createInterpolant){case this.InterpolantFactoryMethodDiscrete:return gs;case this.InterpolantFactoryMethodLinear:return _s;case this.InterpolantFactoryMethodSmooth:return no}}getValueSize(){return this.values.length/this.times.length}shift(e){if(e!==0){const t=this.times;for(let n=0,r=t.length;n!==r;++n)t[n]+=e}return this}scale(e){if(e!==1){const t=this.times;for(let n=0,r=t.length;n!==r;++n)t[n]*=e}return this}trim(e,t){const n=this.times,r=n.length;let s=0,a=r-1;for(;s!==r&&n[s]<e;)++s;for(;a!==-1&&n[a]>t;)--a;if(++a,s!==0||a!==r){s>=a&&(a=Math.max(a,1),s=a-1);const o=this.getValueSize();this.times=n.slice(s,a),this.values=this.values.slice(s*o,a*o)}return this}validate(){let e=!0;const t=this.getValueSize();t-Math.floor(t)!==0&&(console.error("THREE.KeyframeTrack: Invalid value size in track.",this),e=!1);const n=this.times,r=this.values,s=n.length;s===0&&(console.error("THREE.KeyframeTrack: Track is empty.",this),e=!1);let a=null;for(let o=0;o!==s;o++){const l=n[o];if(typeof l=="number"&&isNaN(l)){console.error("THREE.KeyframeTrack: Time is not a valid number.",this,o,l),e=!1;break}if(a!==null&&a>l){console.error("THREE.KeyframeTrack: Out of order keys.",this,o,l,a),e=!1;break}a=l}if(r!==void 0&&Kp(r))for(let o=0,l=r.length;o!==l;++o){const c=r[o];if(isNaN(c)){console.error("THREE.KeyframeTrack: Value is not a valid number.",this,o,c),e=!1;break}}return e}optimize(){const e=this.times.slice(),t=this.values.slice(),n=this.getValueSize(),r=this.getInterpolation()===no,s=e.length-1;let a=1;for(let o=1;o<s;++o){let l=!1;const c=e[o],h=e[o+1];if(c!==h&&(o!==1||c!==e[0]))if(r)l=!0;else{const u=o*n,f=u-n,p=u+n;for(let _=0;_!==n;++_){const y=t[u+_];if(y!==t[f+_]||y!==t[p+_]){l=!0;break}}}if(l){if(o!==a){e[a]=e[o];const u=o*n,f=a*n;for(let p=0;p!==n;++p)t[f+p]=t[u+p]}++a}}if(s>0){e[a]=e[s];for(let o=s*n,l=a*n,c=0;c!==n;++c)t[l+c]=t[o+c];++a}return a!==e.length?(this.times=e.slice(0,a),this.values=t.slice(0,a*n)):(this.times=e,this.values=t),this}clone(){const e=this.times.slice(),t=this.values.slice(),n=this.constructor,r=new n(this.name,e,t);return r.createInterpolant=this.createInterpolant,r}}Tn.prototype.ValueTypeName="";Tn.prototype.TimeBufferType=Float32Array;Tn.prototype.ValueBufferType=Float32Array;Tn.prototype.DefaultInterpolation=_s;class Or extends Tn{constructor(e,t,n){super(e,t,n)}}Or.prototype.ValueTypeName="bool";Or.prototype.ValueBufferType=Array;Or.prototype.DefaultInterpolation=gs;Or.prototype.InterpolantFactoryMethodLinear=void 0;Or.prototype.InterpolantFactoryMethodSmooth=void 0;class nh extends Tn{constructor(e,t,n,r){super(e,t,n,r)}}nh.prototype.ValueTypeName="color";class Ar extends Tn{constructor(e,t,n,r){super(e,t,n,r)}}Ar.prototype.ValueTypeName="number";class em extends ws{constructor(e,t,n,r){super(e,t,n,r)}interpolate_(e,t,n,r){const s=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=(n-t)/(r-t);let c=e*o;for(let h=c+o;c!==h;c+=4)En.slerpFlat(s,0,a,c-o,a,c,l);return s}}class Rr extends Tn{constructor(e,t,n,r){super(e,t,n,r)}InterpolantFactoryMethodLinear(e){return new em(this.times,this.values,this.getValueSize(),e)}}Rr.prototype.ValueTypeName="quaternion";Rr.prototype.InterpolantFactoryMethodSmooth=void 0;class Br extends Tn{constructor(e,t,n){super(e,t,n)}}Br.prototype.ValueTypeName="string";Br.prototype.ValueBufferType=Array;Br.prototype.DefaultInterpolation=gs;Br.prototype.InterpolantFactoryMethodLinear=void 0;Br.prototype.InterpolantFactoryMethodSmooth=void 0;class Cr extends Tn{constructor(e,t,n,r){super(e,t,n,r)}}Cr.prototype.ValueTypeName="vector";class tm{constructor(e="",t=-1,n=[],r=Lf){this.name=e,this.tracks=n,this.duration=t,this.blendMode=r,this.uuid=bn(),this.duration<0&&this.resetDuration()}static parse(e){const t=[],n=e.tracks,r=1/(e.fps||1);for(let a=0,o=n.length;a!==o;++a)t.push(im(n[a]).scale(r));const s=new this(e.name,e.duration,t,e.blendMode);return s.uuid=e.uuid,s}static toJSON(e){const t=[],n=e.tracks,r={name:e.name,duration:e.duration,tracks:t,uuid:e.uuid,blendMode:e.blendMode};for(let s=0,a=n.length;s!==a;++s)t.push(Tn.toJSON(n[s]));return r}static CreateFromMorphTargetSequence(e,t,n,r){const s=t.length,a=[];for(let o=0;o<s;o++){let l=[],c=[];l.push((o+s-1)%s,o,(o+1)%s),c.push(0,1,0);const h=$p(l);l=Cd(l,1,h),c=Cd(c,1,h),!r&&l[0]===0&&(l.push(s),c.push(c[0])),a.push(new Ar(".morphTargetInfluences["+t[o].name+"]",l,c).scale(1/n))}return new this(e,-1,a)}static findByName(e,t){let n=e;if(!Array.isArray(e)){const r=e;n=r.geometry&&r.geometry.animations||r.animations}for(let r=0;r<n.length;r++)if(n[r].name===t)return n[r];return null}static CreateClipsFromMorphTargetSequences(e,t,n){const r={},s=/^([\w-]*?)([\d]+)$/;for(let o=0,l=e.length;o<l;o++){const c=e[o],h=c.name.match(s);if(h&&h.length>1){const u=h[1];let f=r[u];f||(r[u]=f=[]),f.push(c)}}const a=[];for(const o in r)a.push(this.CreateFromMorphTargetSequence(o,r[o],t,n));return a}static parseAnimation(e,t){if(console.warn("THREE.AnimationClip: parseAnimation() is deprecated and will be removed with r185"),!e)return console.error("THREE.AnimationClip: No animation in JSONLoader data."),null;const n=function(u,f,p,_,y){if(p.length!==0){const g=[],m=[];th(p,g,m,_),g.length!==0&&y.push(new u(f,g,m))}},r=[],s=e.name||"default",a=e.fps||30,o=e.blendMode;let l=e.length||-1;const c=e.hierarchy||[];for(let u=0;u<c.length;u++){const f=c[u].keys;if(!(!f||f.length===0))if(f[0].morphTargets){const p={};let _;for(_=0;_<f.length;_++)if(f[_].morphTargets)for(let y=0;y<f[_].morphTargets.length;y++)p[f[_].morphTargets[y]]=-1;for(const y in p){const g=[],m=[];for(let E=0;E!==f[_].morphTargets.length;++E){const w=f[_];g.push(w.time),m.push(w.morphTarget===y?1:0)}r.push(new Ar(".morphTargetInfluence["+y+"]",g,m))}l=p.length*a}else{const p=".bones["+t[u].name+"]";n(Cr,p+".position",f,"pos",r),n(Rr,p+".quaternion",f,"rot",r),n(Cr,p+".scale",f,"scl",r)}}return r.length===0?null:new this(s,l,r,o)}resetDuration(){const e=this.tracks;let t=0;for(let n=0,r=e.length;n!==r;++n){const s=this.tracks[n];t=Math.max(t,s.times[s.times.length-1])}return this.duration=t,this}trim(){for(let e=0;e<this.tracks.length;e++)this.tracks[e].trim(0,this.duration);return this}validate(){let e=!0;for(let t=0;t<this.tracks.length;t++)e=e&&this.tracks[t].validate();return e}optimize(){for(let e=0;e<this.tracks.length;e++)this.tracks[e].optimize();return this}clone(){const e=[];for(let t=0;t<this.tracks.length;t++)e.push(this.tracks[t].clone());return new this.constructor(this.name,this.duration,e,this.blendMode)}toJSON(){return this.constructor.toJSON(this)}}function nm(i){switch(i.toLowerCase()){case"scalar":case"double":case"float":case"number":case"integer":return Ar;case"vector":case"vector2":case"vector3":case"vector4":return Cr;case"color":return nh;case"quaternion":return Rr;case"bool":case"boolean":return Or;case"string":return Br}throw new Error("THREE.KeyframeTrack: Unsupported typeName: "+i)}function im(i){if(i.type===void 0)throw new Error("THREE.KeyframeTrack: track type undefined, can not parse");const e=nm(i.type);if(i.times===void 0){const t=[],n=[];th(i.keys,t,n,"value"),i.times=t,i.values=n}return e.parse!==void 0?e.parse(i):new e(i.name,i.times,i.values,i.interpolation)}const $n={enabled:!1,files:{},add:function(i,e){this.enabled!==!1&&(this.files[i]=e)},get:function(i){if(this.enabled!==!1)return this.files[i]},remove:function(i){delete this.files[i]},clear:function(){this.files={}}};class rm{constructor(e,t,n){const r=this;let s=!1,a=0,o=0,l;const c=[];this.onStart=void 0,this.onLoad=e,this.onProgress=t,this.onError=n,this.abortController=new AbortController,this.itemStart=function(h){o++,s===!1&&r.onStart!==void 0&&r.onStart(h,a,o),s=!0},this.itemEnd=function(h){a++,r.onProgress!==void 0&&r.onProgress(h,a,o),a===o&&(s=!1,r.onLoad!==void 0&&r.onLoad())},this.itemError=function(h){r.onError!==void 0&&r.onError(h)},this.resolveURL=function(h){return l?l(h):h},this.setURLModifier=function(h){return l=h,this},this.addHandler=function(h,u){return c.push(h,u),this},this.removeHandler=function(h){const u=c.indexOf(h);return u!==-1&&c.splice(u,2),this},this.getHandler=function(h){for(let u=0,f=c.length;u<f;u+=2){const p=c[u],_=c[u+1];if(p.global&&(p.lastIndex=0),p.test(h))return _}return null},this.abort=function(){return this.abortController.abort(),this.abortController=new AbortController,this}}}const sm=new rm;class Bi{constructor(e){this.manager=e!==void 0?e:sm,this.crossOrigin="anonymous",this.withCredentials=!1,this.path="",this.resourcePath="",this.requestHeader={}}load(){}loadAsync(e,t){const n=this;return new Promise(function(r,s){n.load(e,r,t,s)})}parse(){}setCrossOrigin(e){return this.crossOrigin=e,this}setWithCredentials(e){return this.withCredentials=e,this}setPath(e){return this.path=e,this}setResourcePath(e){return this.resourcePath=e,this}setRequestHeader(e){return this.requestHeader=e,this}abort(){return this}}Bi.DEFAULT_MATERIAL_NAME="__DEFAULT";const Vn={};class am extends Error{constructor(e,t){super(e),this.response=t}}class cc extends Bi{constructor(e){super(e),this.mimeType="",this.responseType="",this._abortController=new AbortController}load(e,t,n,r){e===void 0&&(e=""),this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);const s=$n.get(`file:${e}`);if(s!==void 0)return this.manager.itemStart(e),setTimeout(()=>{t&&t(s),this.manager.itemEnd(e)},0),s;if(Vn[e]!==void 0){Vn[e].push({onLoad:t,onProgress:n,onError:r});return}Vn[e]=[],Vn[e].push({onLoad:t,onProgress:n,onError:r});const a=new Request(e,{headers:new Headers(this.requestHeader),credentials:this.withCredentials?"include":"same-origin",signal:typeof AbortSignal.any=="function"?AbortSignal.any([this._abortController.signal,this.manager.abortController.signal]):this._abortController.signal}),o=this.mimeType,l=this.responseType;fetch(a).then(c=>{if(c.status===200||c.status===0){if(c.status===0&&console.warn("THREE.FileLoader: HTTP Status 0 received."),typeof ReadableStream>"u"||c.body===void 0||c.body.getReader===void 0)return c;const h=Vn[e],u=c.body.getReader(),f=c.headers.get("X-File-Size")||c.headers.get("Content-Length"),p=f?parseInt(f):0,_=p!==0;let y=0;const g=new ReadableStream({start(m){E();function E(){u.read().then(({done:w,value:x})=>{if(w)m.close();else{y+=x.byteLength;const T=new ProgressEvent("progress",{lengthComputable:_,loaded:y,total:p});for(let L=0,C=h.length;L<C;L++){const R=h[L];R.onProgress&&R.onProgress(T)}m.enqueue(x),E()}},w=>{m.error(w)})}}});return new Response(g)}else throw new am(`fetch for "${c.url}" responded with ${c.status}: ${c.statusText}`,c)}).then(c=>{switch(l){case"arraybuffer":return c.arrayBuffer();case"blob":return c.blob();case"document":return c.text().then(h=>new DOMParser().parseFromString(h,o));case"json":return c.json();default:if(o==="")return c.text();{const u=/charset="?([^;"\s]*)"?/i.exec(o),f=u&&u[1]?u[1].toLowerCase():void 0,p=new TextDecoder(f);return c.arrayBuffer().then(_=>p.decode(_))}}}).then(c=>{$n.add(`file:${e}`,c);const h=Vn[e];delete Vn[e];for(let u=0,f=h.length;u<f;u++){const p=h[u];p.onLoad&&p.onLoad(c)}}).catch(c=>{const h=Vn[e];if(h===void 0)throw this.manager.itemError(e),c;delete Vn[e];for(let u=0,f=h.length;u<f;u++){const p=h[u];p.onError&&p.onError(c)}this.manager.itemError(e)}).finally(()=>{this.manager.itemEnd(e)}),this.manager.itemStart(e)}setResponseType(e){return this.responseType=e,this}setMimeType(e){return this.mimeType=e,this}abort(){return this._abortController.abort(),this._abortController=new AbortController,this}}const sr=new WeakMap;class om extends Bi{constructor(e){super(e)}load(e,t,n,r){this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);const s=this,a=$n.get(`image:${e}`);if(a!==void 0){if(a.complete===!0)s.manager.itemStart(e),setTimeout(function(){t&&t(a),s.manager.itemEnd(e)},0);else{let u=sr.get(a);u===void 0&&(u=[],sr.set(a,u)),u.push({onLoad:t,onError:r})}return a}const o=ys("img");function l(){h(),t&&t(this);const u=sr.get(this)||[];for(let f=0;f<u.length;f++){const p=u[f];p.onLoad&&p.onLoad(this)}sr.delete(this),s.manager.itemEnd(e)}function c(u){h(),r&&r(u),$n.remove(`image:${e}`);const f=sr.get(this)||[];for(let p=0;p<f.length;p++){const _=f[p];_.onError&&_.onError(u)}sr.delete(this),s.manager.itemError(e),s.manager.itemEnd(e)}function h(){o.removeEventListener("load",l,!1),o.removeEventListener("error",c,!1)}return o.addEventListener("load",l,!1),o.addEventListener("error",c,!1),e.slice(0,5)!=="data:"&&this.crossOrigin!==void 0&&(o.crossOrigin=this.crossOrigin),$n.add(`image:${e}`,o),s.manager.itemStart(e),o.src=e,o}}class lm extends Bi{constructor(e){super(e)}load(e,t,n,r){const s=this,a=new Wa,o=new cc(this.manager);return o.setResponseType("arraybuffer"),o.setRequestHeader(this.requestHeader),o.setPath(this.path),o.setWithCredentials(s.withCredentials),o.load(e,function(l){let c;try{c=s.parse(l)}catch(h){if(r!==void 0)r(h);else{console.error(h);return}}c.image!==void 0?a.image=c.image:c.data!==void 0&&(a.image.width=c.width,a.image.height=c.height,a.image.data=c.data),a.wrapS=c.wrapS!==void 0?c.wrapS:Cn,a.wrapT=c.wrapT!==void 0?c.wrapT:Cn,a.magFilter=c.magFilter!==void 0?c.magFilter:Tt,a.minFilter=c.minFilter!==void 0?c.minFilter:Tt,a.anisotropy=c.anisotropy!==void 0?c.anisotropy:1,c.colorSpace!==void 0&&(a.colorSpace=c.colorSpace),c.flipY!==void 0&&(a.flipY=c.flipY),c.format!==void 0&&(a.format=c.format),c.type!==void 0&&(a.type=c.type),c.mipmaps!==void 0&&(a.mipmaps=c.mipmaps,a.minFilter=Pn),c.mipmapCount===1&&(a.minFilter=Tt),c.generateMipmaps!==void 0&&(a.generateMipmaps=c.generateMipmaps),a.needsUpdate=!0,t&&t(a,c)},n,r),a}}class ih extends Bi{constructor(e){super(e)}load(e,t,n,r){const s=new Ct,a=new om(this.manager);return a.setCrossOrigin(this.crossOrigin),a.setPath(this.path),a.load(e,function(o){s.image=o,s.needsUpdate=!0,t!==void 0&&t(s)},n,r),s}}class Es extends pt{constructor(e,t=1){super(),this.isLight=!0,this.type="Light",this.color=new Ee(e),this.intensity=t}dispose(){}copy(e,t){return super.copy(e,t),this.color.copy(e.color),this.intensity=e.intensity,this}toJSON(e){const t=super.toJSON(e);return t.object.color=this.color.getHex(),t.object.intensity=this.intensity,this.groundColor!==void 0&&(t.object.groundColor=this.groundColor.getHex()),this.distance!==void 0&&(t.object.distance=this.distance),this.angle!==void 0&&(t.object.angle=this.angle),this.decay!==void 0&&(t.object.decay=this.decay),this.penumbra!==void 0&&(t.object.penumbra=this.penumbra),this.shadow!==void 0&&(t.object.shadow=this.shadow.toJSON()),this.target!==void 0&&(t.object.target=this.target.uuid),t}}class cm extends Es{constructor(e,t,n){super(e,n),this.isHemisphereLight=!0,this.type="HemisphereLight",this.position.copy(pt.DEFAULT_UP),this.updateMatrix(),this.groundColor=new Ee(t)}copy(e,t){return super.copy(e,t),this.groundColor.copy(e.groundColor),this}}const Io=new De,Pd=new P,Id=new P;class dc{constructor(e){this.camera=e,this.intensity=1,this.bias=0,this.normalBias=0,this.radius=1,this.blurSamples=8,this.mapSize=new xe(512,512),this.mapType=Sn,this.map=null,this.mapPass=null,this.matrix=new De,this.autoUpdate=!0,this.needsUpdate=!1,this._frustum=new Xa,this._frameExtents=new xe(1,1),this._viewportCount=1,this._viewports=[new Ye(0,0,1,1)]}getViewportCount(){return this._viewportCount}getFrustum(){return this._frustum}updateMatrices(e){const t=this.camera,n=this.matrix;Pd.setFromMatrixPosition(e.matrixWorld),t.position.copy(Pd),Id.setFromMatrixPosition(e.target.matrixWorld),t.lookAt(Id),t.updateMatrixWorld(),Io.multiplyMatrices(t.projectionMatrix,t.matrixWorldInverse),this._frustum.setFromProjectionMatrix(Io,t.coordinateSystem,t.reversedDepth),t.reversedDepth?n.set(.5,0,0,.5,0,.5,0,.5,0,0,1,0,0,0,0,1):n.set(.5,0,0,.5,0,.5,0,.5,0,0,.5,.5,0,0,0,1),n.multiply(Io)}getViewport(e){return this._viewports[e]}getFrameExtents(){return this._frameExtents}dispose(){this.map&&this.map.dispose(),this.mapPass&&this.mapPass.dispose()}copy(e){return this.camera=e.camera.clone(),this.intensity=e.intensity,this.bias=e.bias,this.radius=e.radius,this.autoUpdate=e.autoUpdate,this.needsUpdate=e.needsUpdate,this.normalBias=e.normalBias,this.blurSamples=e.blurSamples,this.mapSize.copy(e.mapSize),this}clone(){return new this.constructor().copy(this)}toJSON(){const e={};return this.intensity!==1&&(e.intensity=this.intensity),this.bias!==0&&(e.bias=this.bias),this.normalBias!==0&&(e.normalBias=this.normalBias),this.radius!==1&&(e.radius=this.radius),(this.mapSize.x!==512||this.mapSize.y!==512)&&(e.mapSize=this.mapSize.toArray()),e.camera=this.camera.toJSON(!1).object,delete e.camera.matrix,e}}class dm extends dc{constructor(){super(new Xt(50,1,.5,500)),this.isSpotLightShadow=!0,this.focus=1,this.aspect=1}updateMatrices(e){const t=this.camera,n=Er*2*e.angle*this.focus,r=this.mapSize.width/this.mapSize.height*this.aspect,s=e.distance||t.far;(n!==t.fov||r!==t.aspect||s!==t.far)&&(t.fov=n,t.aspect=r,t.far=s,t.updateProjectionMatrix()),super.updateMatrices(e)}copy(e){return super.copy(e),this.focus=e.focus,this}}class um extends Es{constructor(e,t,n=0,r=Math.PI/3,s=0,a=2){super(e,t),this.isSpotLight=!0,this.type="SpotLight",this.position.copy(pt.DEFAULT_UP),this.updateMatrix(),this.target=new pt,this.distance=n,this.angle=r,this.penumbra=s,this.decay=a,this.map=null,this.shadow=new dm}get power(){return this.intensity*Math.PI}set power(e){this.intensity=e/Math.PI}dispose(){this.shadow.dispose()}copy(e,t){return super.copy(e,t),this.distance=e.distance,this.angle=e.angle,this.penumbra=e.penumbra,this.decay=e.decay,this.target=e.target.clone(),this.shadow=e.shadow.clone(),this}}const Ld=new De,Qr=new P,Lo=new P;class hm extends dc{constructor(){super(new Xt(90,1,.5,500)),this.isPointLightShadow=!0,this._frameExtents=new xe(4,2),this._viewportCount=6,this._viewports=[new Ye(2,1,1,1),new Ye(0,1,1,1),new Ye(3,1,1,1),new Ye(1,1,1,1),new Ye(3,0,1,1),new Ye(1,0,1,1)],this._cubeDirections=[new P(1,0,0),new P(-1,0,0),new P(0,0,1),new P(0,0,-1),new P(0,1,0),new P(0,-1,0)],this._cubeUps=[new P(0,1,0),new P(0,1,0),new P(0,1,0),new P(0,1,0),new P(0,0,1),new P(0,0,-1)]}updateMatrices(e,t=0){const n=this.camera,r=this.matrix,s=e.distance||n.far;s!==n.far&&(n.far=s,n.updateProjectionMatrix()),Qr.setFromMatrixPosition(e.matrixWorld),n.position.copy(Qr),Lo.copy(n.position),Lo.add(this._cubeDirections[t]),n.up.copy(this._cubeUps[t]),n.lookAt(Lo),n.updateMatrixWorld(),r.makeTranslation(-Qr.x,-Qr.y,-Qr.z),Ld.multiplyMatrices(n.projectionMatrix,n.matrixWorldInverse),this._frustum.setFromProjectionMatrix(Ld,n.coordinateSystem,n.reversedDepth)}}class rh extends Es{constructor(e,t,n=0,r=2){super(e,t),this.isPointLight=!0,this.type="PointLight",this.distance=n,this.decay=r,this.shadow=new hm}get power(){return this.intensity*4*Math.PI}set power(e){this.intensity=e/(4*Math.PI)}dispose(){this.shadow.dispose()}copy(e,t){return super.copy(e,t),this.distance=e.distance,this.decay=e.decay,this.shadow=e.shadow.clone(),this}}class uc extends Xu{constructor(e=-1,t=1,n=1,r=-1,s=.1,a=2e3){super(),this.isOrthographicCamera=!0,this.type="OrthographicCamera",this.zoom=1,this.view=null,this.left=e,this.right=t,this.top=n,this.bottom=r,this.near=s,this.far=a,this.updateProjectionMatrix()}copy(e,t){return super.copy(e,t),this.left=e.left,this.right=e.right,this.top=e.top,this.bottom=e.bottom,this.near=e.near,this.far=e.far,this.zoom=e.zoom,this.view=e.view===null?null:Object.assign({},e.view),this}setViewOffset(e,t,n,r,s,a){this.view===null&&(this.view={enabled:!0,fullWidth:1,fullHeight:1,offsetX:0,offsetY:0,width:1,height:1}),this.view.enabled=!0,this.view.fullWidth=e,this.view.fullHeight=t,this.view.offsetX=n,this.view.offsetY=r,this.view.width=s,this.view.height=a,this.updateProjectionMatrix()}clearViewOffset(){this.view!==null&&(this.view.enabled=!1),this.updateProjectionMatrix()}updateProjectionMatrix(){const e=(this.right-this.left)/(2*this.zoom),t=(this.top-this.bottom)/(2*this.zoom),n=(this.right+this.left)/2,r=(this.top+this.bottom)/2;let s=n-e,a=n+e,o=r+t,l=r-t;if(this.view!==null&&this.view.enabled){const c=(this.right-this.left)/this.view.fullWidth/this.zoom,h=(this.top-this.bottom)/this.view.fullHeight/this.zoom;s+=c*this.view.offsetX,a=s+c*this.view.width,o-=h*this.view.offsetY,l=o-h*this.view.height}this.projectionMatrix.makeOrthographic(s,a,o,l,this.near,this.far,this.coordinateSystem,this.reversedDepth),this.projectionMatrixInverse.copy(this.projectionMatrix).invert()}toJSON(e){const t=super.toJSON(e);return t.object.zoom=this.zoom,t.object.left=this.left,t.object.right=this.right,t.object.top=this.top,t.object.bottom=this.bottom,t.object.near=this.near,t.object.far=this.far,this.view!==null&&(t.object.view=Object.assign({},this.view)),t}}class fm extends dc{constructor(){super(new uc(-5,5,5,-5,.5,500)),this.isDirectionalLightShadow=!0}}class sh extends Es{constructor(e,t){super(e,t),this.isDirectionalLight=!0,this.type="DirectionalLight",this.position.copy(pt.DEFAULT_UP),this.updateMatrix(),this.target=new pt,this.shadow=new fm}dispose(){this.shadow.dispose()}copy(e){return super.copy(e),this.target=e.target.clone(),this.shadow=e.shadow.clone(),this}}class pm extends Es{constructor(e,t){super(e,t),this.isAmbientLight=!0,this.type="AmbientLight"}}class cs{static extractUrlBase(e){const t=e.lastIndexOf("/");return t===-1?"./":e.slice(0,t+1)}static resolveURL(e,t){return typeof e!="string"||e===""?"":(/^https?:\/\//i.test(t)&&/^\//.test(e)&&(t=t.replace(/(^https?:\/\/[^\/]+).*/i,"$1")),/^(https?:)?\/\//i.test(e)||/^data:.*,.*$/i.test(e)||/^blob:.*$/i.test(e)?e:t+e)}}const Do=new WeakMap;class mm extends Bi{constructor(e){super(e),this.isImageBitmapLoader=!0,typeof createImageBitmap>"u"&&console.warn("THREE.ImageBitmapLoader: createImageBitmap() not supported."),typeof fetch>"u"&&console.warn("THREE.ImageBitmapLoader: fetch() not supported."),this.options={premultiplyAlpha:"none"},this._abortController=new AbortController}setOptions(e){return this.options=e,this}load(e,t,n,r){e===void 0&&(e=""),this.path!==void 0&&(e=this.path+e),e=this.manager.resolveURL(e);const s=this,a=$n.get(`image-bitmap:${e}`);if(a!==void 0){if(s.manager.itemStart(e),a.then){a.then(c=>{if(Do.has(a)===!0)r&&r(Do.get(a)),s.manager.itemError(e),s.manager.itemEnd(e);else return t&&t(c),s.manager.itemEnd(e),c});return}return setTimeout(function(){t&&t(a),s.manager.itemEnd(e)},0),a}const o={};o.credentials=this.crossOrigin==="anonymous"?"same-origin":"include",o.headers=this.requestHeader,o.signal=typeof AbortSignal.any=="function"?AbortSignal.any([this._abortController.signal,this.manager.abortController.signal]):this._abortController.signal;const l=fetch(e,o).then(function(c){return c.blob()}).then(function(c){return createImageBitmap(c,Object.assign(s.options,{colorSpaceConversion:"none"}))}).then(function(c){return $n.add(`image-bitmap:${e}`,c),t&&t(c),s.manager.itemEnd(e),c}).catch(function(c){r&&r(c),Do.set(l,c),$n.remove(`image-bitmap:${e}`),s.manager.itemError(e),s.manager.itemEnd(e)});$n.add(`image-bitmap:${e}`,l),s.manager.itemStart(e)}abort(){return this._abortController.abort(),this._abortController=new AbortController,this}}class gm extends Xt{constructor(e=[]){super(),this.isArrayCamera=!0,this.isMultiViewCamera=!1,this.cameras=e}}const hc="\\[\\]\\.:\\/",_m=new RegExp("["+hc+"]","g"),fc="[^"+hc+"]",ym="[^"+hc.replace("\\.","")+"]",xm=/((?:WC+[\/:])*)/.source.replace("WC",fc),vm=/(WCOD+)?/.source.replace("WCOD",ym),Mm=/(?:\.(WC+)(?:\[(.+)\])?)?/.source.replace("WC",fc),bm=/\.(WC+)(?:\[(.+)\])?/.source.replace("WC",fc),Sm=new RegExp("^"+xm+vm+Mm+bm+"$"),wm=["material","materials","bones","map"];class Em{constructor(e,t,n){const r=n||at.parseTrackName(t);this._targetGroup=e,this._bindings=e.subscribe_(t,r)}getValue(e,t){this.bind();const n=this._targetGroup.nCachedObjects_,r=this._bindings[n];r!==void 0&&r.getValue(e,t)}setValue(e,t){const n=this._bindings;for(let r=this._targetGroup.nCachedObjects_,s=n.length;r!==s;++r)n[r].setValue(e,t)}bind(){const e=this._bindings;for(let t=this._targetGroup.nCachedObjects_,n=e.length;t!==n;++t)e[t].bind()}unbind(){const e=this._bindings;for(let t=this._targetGroup.nCachedObjects_,n=e.length;t!==n;++t)e[t].unbind()}}class at{constructor(e,t,n){this.path=t,this.parsedPath=n||at.parseTrackName(t),this.node=at.findNode(e,this.parsedPath.nodeName),this.rootNode=e,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}static create(e,t,n){return e&&e.isAnimationObjectGroup?new at.Composite(e,t,n):new at(e,t,n)}static sanitizeNodeName(e){return e.replace(/\s/g,"_").replace(_m,"")}static parseTrackName(e){const t=Sm.exec(e);if(t===null)throw new Error("PropertyBinding: Cannot parse trackName: "+e);const n={nodeName:t[2],objectName:t[3],objectIndex:t[4],propertyName:t[5],propertyIndex:t[6]},r=n.nodeName&&n.nodeName.lastIndexOf(".");if(r!==void 0&&r!==-1){const s=n.nodeName.substring(r+1);wm.indexOf(s)!==-1&&(n.nodeName=n.nodeName.substring(0,r),n.objectName=s)}if(n.propertyName===null||n.propertyName.length===0)throw new Error("PropertyBinding: can not parse propertyName from trackName: "+e);return n}static findNode(e,t){if(t===void 0||t===""||t==="."||t===-1||t===e.name||t===e.uuid)return e;if(e.skeleton){const n=e.skeleton.getBoneByName(t);if(n!==void 0)return n}if(e.children){const n=function(s){for(let a=0;a<s.length;a++){const o=s[a];if(o.name===t||o.uuid===t)return o;const l=n(o.children);if(l)return l}return null},r=n(e.children);if(r)return r}return null}_getValue_unavailable(){}_setValue_unavailable(){}_getValue_direct(e,t){e[t]=this.targetObject[this.propertyName]}_getValue_array(e,t){const n=this.resolvedProperty;for(let r=0,s=n.length;r!==s;++r)e[t++]=n[r]}_getValue_arrayElement(e,t){e[t]=this.resolvedProperty[this.propertyIndex]}_getValue_toArray(e,t){this.resolvedProperty.toArray(e,t)}_setValue_direct(e,t){this.targetObject[this.propertyName]=e[t]}_setValue_direct_setNeedsUpdate(e,t){this.targetObject[this.propertyName]=e[t],this.targetObject.needsUpdate=!0}_setValue_direct_setMatrixWorldNeedsUpdate(e,t){this.targetObject[this.propertyName]=e[t],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_array(e,t){const n=this.resolvedProperty;for(let r=0,s=n.length;r!==s;++r)n[r]=e[t++]}_setValue_array_setNeedsUpdate(e,t){const n=this.resolvedProperty;for(let r=0,s=n.length;r!==s;++r)n[r]=e[t++];this.targetObject.needsUpdate=!0}_setValue_array_setMatrixWorldNeedsUpdate(e,t){const n=this.resolvedProperty;for(let r=0,s=n.length;r!==s;++r)n[r]=e[t++];this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_arrayElement(e,t){this.resolvedProperty[this.propertyIndex]=e[t]}_setValue_arrayElement_setNeedsUpdate(e,t){this.resolvedProperty[this.propertyIndex]=e[t],this.targetObject.needsUpdate=!0}_setValue_arrayElement_setMatrixWorldNeedsUpdate(e,t){this.resolvedProperty[this.propertyIndex]=e[t],this.targetObject.matrixWorldNeedsUpdate=!0}_setValue_fromArray(e,t){this.resolvedProperty.fromArray(e,t)}_setValue_fromArray_setNeedsUpdate(e,t){this.resolvedProperty.fromArray(e,t),this.targetObject.needsUpdate=!0}_setValue_fromArray_setMatrixWorldNeedsUpdate(e,t){this.resolvedProperty.fromArray(e,t),this.targetObject.matrixWorldNeedsUpdate=!0}_getValue_unbound(e,t){this.bind(),this.getValue(e,t)}_setValue_unbound(e,t){this.bind(),this.setValue(e,t)}bind(){let e=this.node;const t=this.parsedPath,n=t.objectName,r=t.propertyName;let s=t.propertyIndex;if(e||(e=at.findNode(this.rootNode,t.nodeName),this.node=e),this.getValue=this._getValue_unavailable,this.setValue=this._setValue_unavailable,!e){console.warn("THREE.PropertyBinding: No target node found for track: "+this.path+".");return}if(n){let c=t.objectIndex;switch(n){case"materials":if(!e.material){console.error("THREE.PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!e.material.materials){console.error("THREE.PropertyBinding: Can not bind to material.materials as node.material does not have a materials array.",this);return}e=e.material.materials;break;case"bones":if(!e.skeleton){console.error("THREE.PropertyBinding: Can not bind to bones as node does not have a skeleton.",this);return}e=e.skeleton.bones;for(let h=0;h<e.length;h++)if(e[h].name===c){c=h;break}break;case"map":if("map"in e){e=e.map;break}if(!e.material){console.error("THREE.PropertyBinding: Can not bind to material as node does not have a material.",this);return}if(!e.material.map){console.error("THREE.PropertyBinding: Can not bind to material.map as node.material does not have a map.",this);return}e=e.material.map;break;default:if(e[n]===void 0){console.error("THREE.PropertyBinding: Can not bind to objectName of node undefined.",this);return}e=e[n]}if(c!==void 0){if(e[c]===void 0){console.error("THREE.PropertyBinding: Trying to bind to objectIndex of objectName, but is undefined.",this,e);return}e=e[c]}}const a=e[r];if(a===void 0){const c=t.nodeName;console.error("THREE.PropertyBinding: Trying to update property for track: "+c+"."+r+" but it wasn't found.",e);return}let o=this.Versioning.None;this.targetObject=e,e.isMaterial===!0?o=this.Versioning.NeedsUpdate:e.isObject3D===!0&&(o=this.Versioning.MatrixWorldNeedsUpdate);let l=this.BindingType.Direct;if(s!==void 0){if(r==="morphTargetInfluences"){if(!e.geometry){console.error("THREE.PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.",this);return}if(!e.geometry.morphAttributes){console.error("THREE.PropertyBinding: Can not bind to morphTargetInfluences because node does not have a geometry.morphAttributes.",this);return}e.morphTargetDictionary[s]!==void 0&&(s=e.morphTargetDictionary[s])}l=this.BindingType.ArrayElement,this.resolvedProperty=a,this.propertyIndex=s}else a.fromArray!==void 0&&a.toArray!==void 0?(l=this.BindingType.HasFromToArray,this.resolvedProperty=a):Array.isArray(a)?(l=this.BindingType.EntireArray,this.resolvedProperty=a):this.propertyName=r;this.getValue=this.GetterByBindingType[l],this.setValue=this.SetterByBindingTypeAndVersioning[l][o]}unbind(){this.node=null,this.getValue=this._getValue_unbound,this.setValue=this._setValue_unbound}}at.Composite=Em;at.prototype.BindingType={Direct:0,EntireArray:1,ArrayElement:2,HasFromToArray:3};at.prototype.Versioning={None:0,NeedsUpdate:1,MatrixWorldNeedsUpdate:2};at.prototype.GetterByBindingType=[at.prototype._getValue_direct,at.prototype._getValue_array,at.prototype._getValue_arrayElement,at.prototype._getValue_toArray];at.prototype.SetterByBindingTypeAndVersioning=[[at.prototype._setValue_direct,at.prototype._setValue_direct_setNeedsUpdate,at.prototype._setValue_direct_setMatrixWorldNeedsUpdate],[at.prototype._setValue_array,at.prototype._setValue_array_setNeedsUpdate,at.prototype._setValue_array_setMatrixWorldNeedsUpdate],[at.prototype._setValue_arrayElement,at.prototype._setValue_arrayElement_setNeedsUpdate,at.prototype._setValue_arrayElement_setMatrixWorldNeedsUpdate],[at.prototype._setValue_fromArray,at.prototype._setValue_fromArray_setNeedsUpdate,at.prototype._setValue_fromArray_setMatrixWorldNeedsUpdate]];const Dd=new De;class Tm{constructor(e,t,n=0,r=1/0){this.ray=new Fr(e,t),this.near=n,this.far=r,this.camera=null,this.layers=new nc,this.params={Mesh:{},Line:{threshold:1},LOD:{},Points:{threshold:1},Sprite:{}}}set(e,t){this.ray.set(e,t)}setFromCamera(e,t){t.isPerspectiveCamera?(this.ray.origin.setFromMatrixPosition(t.matrixWorld),this.ray.direction.set(e.x,e.y,.5).unproject(t).sub(this.ray.origin).normalize(),this.camera=t):t.isOrthographicCamera?(this.ray.origin.set(e.x,e.y,(t.near+t.far)/(t.near-t.far)).unproject(t),this.ray.direction.set(0,0,-1).transformDirection(t.matrixWorld),this.camera=t):console.error("THREE.Raycaster: Unsupported camera type: "+t.type)}setFromXRController(e){return Dd.identity().extractRotation(e.matrixWorld),this.ray.origin.setFromMatrixPosition(e.matrixWorld),this.ray.direction.set(0,0,-1).applyMatrix4(Dd),this}intersectObject(e,t=!0,n=[]){return Ll(e,this,n,t),n.sort(Nd),n}intersectObjects(e,t=!0,n=[]){for(let r=0,s=e.length;r<s;r++)Ll(e[r],this,n,t);return n.sort(Nd),n}}function Nd(i,e){return i.distance-e.distance}function Ll(i,e,t,n){let r=!0;if(i.layers.test(e.layers)&&i.raycast(e,t)===!1&&(r=!1),r===!0&&n===!0){const s=i.children;for(let a=0,o=s.length;a<o;a++)Ll(s[a],e,t,!0)}}class Ud{constructor(e=1,t=0,n=0){this.radius=e,this.phi=t,this.theta=n}set(e,t,n){return this.radius=e,this.phi=t,this.theta=n,this}copy(e){return this.radius=e.radius,this.phi=e.phi,this.theta=e.theta,this}makeSafe(){return this.phi=Xe(this.phi,1e-6,Math.PI-1e-6),this}setFromVector3(e){return this.setFromCartesianCoords(e.x,e.y,e.z)}setFromCartesianCoords(e,t,n){return this.radius=Math.sqrt(e*e+t*t+n*n),this.radius===0?(this.theta=0,this.phi=0):(this.theta=Math.atan2(e,n),this.phi=Math.acos(Xe(t/this.radius,-1,1))),this}clone(){return new this.constructor().copy(this)}}class ah extends ni{constructor(e,t=16776960){const n=new Uint16Array([0,1,1,2,2,3,3,0,4,5,5,6,6,7,7,4,0,4,1,5,2,6,3,7]),r=[1,1,1,-1,1,1,-1,-1,1,1,-1,1,1,1,-1,-1,1,-1,-1,-1,-1,1,-1,-1],s=new yt;s.setIndex(new Ot(n,1)),s.setAttribute("position",new mt(r,3)),super(s,new Fn({color:t,toneMapped:!1})),this.box=e,this.type="Box3Helper",this.geometry.computeBoundingSphere()}updateMatrixWorld(e){const t=this.box;t.isEmpty()||(t.getCenter(this.position),t.getSize(this.scale),this.scale.multiplyScalar(.5),super.updateMatrixWorld(e))}dispose(){this.geometry.dispose(),this.material.dispose()}}class Am extends Oi{constructor(e,t=null){super(),this.object=e,this.domElement=t,this.enabled=!0,this.state=-1,this.keys={},this.mouseButtons={LEFT:null,MIDDLE:null,RIGHT:null},this.touches={ONE:null,TWO:null}}connect(e){if(e===void 0){console.warn("THREE.Controls: connect() now requires an element.");return}this.domElement!==null&&this.disconnect(),this.domElement=e}disconnect(){}dispose(){}update(){}}function Fd(i,e,t,n){const r=Rm(n);switch(t){case Du:return i*e;case Kl:return i*e/r.components*r.byteLength;case $l:return i*e/r.components*r.byteLength;case Uu:return i*e*2/r.components*r.byteLength;case Zl:return i*e*2/r.components*r.byteLength;case Nu:return i*e*3/r.components*r.byteLength;case sn:return i*e*4/r.components*r.byteLength;case Jl:return i*e*4/r.components*r.byteLength;case va:case Ma:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*8;case ba:case Sa:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case il:case sl:return Math.max(i,16)*Math.max(e,8)/4;case nl:case rl:return Math.max(i,8)*Math.max(e,8)/2;case al:case ol:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*8;case ll:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case cl:return Math.floor((i+3)/4)*Math.floor((e+3)/4)*16;case dl:return Math.floor((i+4)/5)*Math.floor((e+3)/4)*16;case ul:return Math.floor((i+4)/5)*Math.floor((e+4)/5)*16;case hl:return Math.floor((i+5)/6)*Math.floor((e+4)/5)*16;case fl:return Math.floor((i+5)/6)*Math.floor((e+5)/6)*16;case pl:return Math.floor((i+7)/8)*Math.floor((e+4)/5)*16;case ml:return Math.floor((i+7)/8)*Math.floor((e+5)/6)*16;case gl:return Math.floor((i+7)/8)*Math.floor((e+7)/8)*16;case _l:return Math.floor((i+9)/10)*Math.floor((e+4)/5)*16;case yl:return Math.floor((i+9)/10)*Math.floor((e+5)/6)*16;case xl:return Math.floor((i+9)/10)*Math.floor((e+7)/8)*16;case vl:return Math.floor((i+9)/10)*Math.floor((e+9)/10)*16;case Ml:return Math.floor((i+11)/12)*Math.floor((e+9)/10)*16;case bl:return Math.floor((i+11)/12)*Math.floor((e+11)/12)*16;case wa:case Sl:case wl:return Math.ceil(i/4)*Math.ceil(e/4)*16;case Fu:case El:return Math.ceil(i/4)*Math.ceil(e/4)*8;case Tl:case Al:return Math.ceil(i/4)*Math.ceil(e/4)*16}throw new Error(`Unable to determine texture byte length for ${t} format.`)}function Rm(i){switch(i){case Sn:case Pu:return{byteLength:1,components:1};case hs:case Iu:case In:return{byteLength:2,components:1};case ql:case Yl:return{byteLength:2,components:4};case Di:case jl:case $t:return{byteLength:4,components:1};case Lu:return{byteLength:4,components:3}}throw new Error(`Unknown texture type ${i}.`)}typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("register",{detail:{revision:Wl}}));typeof window<"u"&&(window.__THREE__?console.warn("WARNING: Multiple instances of Three.js being imported."):window.__THREE__=Wl);function oh(){let i=null,e=!1,t=null,n=null;function r(s,a){t(s,a),n=i.requestAnimationFrame(r)}return{start:function(){e!==!0&&t!==null&&(n=i.requestAnimationFrame(r),e=!0)},stop:function(){i.cancelAnimationFrame(n),e=!1},setAnimationLoop:function(s){t=s},setContext:function(s){i=s}}}function Cm(i){const e=new WeakMap;function t(o,l){const c=o.array,h=o.usage,u=c.byteLength,f=i.createBuffer();i.bindBuffer(l,f),i.bufferData(l,c,h),o.onUploadCallback();let p;if(c instanceof Float32Array)p=i.FLOAT;else if(typeof Float16Array<"u"&&c instanceof Float16Array)p=i.HALF_FLOAT;else if(c instanceof Uint16Array)o.isFloat16BufferAttribute?p=i.HALF_FLOAT:p=i.UNSIGNED_SHORT;else if(c instanceof Int16Array)p=i.SHORT;else if(c instanceof Uint32Array)p=i.UNSIGNED_INT;else if(c instanceof Int32Array)p=i.INT;else if(c instanceof Int8Array)p=i.BYTE;else if(c instanceof Uint8Array)p=i.UNSIGNED_BYTE;else if(c instanceof Uint8ClampedArray)p=i.UNSIGNED_BYTE;else throw new Error("THREE.WebGLAttributes: Unsupported buffer data format: "+c);return{buffer:f,type:p,bytesPerElement:c.BYTES_PER_ELEMENT,version:o.version,size:u}}function n(o,l,c){const h=l.array,u=l.updateRanges;if(i.bindBuffer(c,o),u.length===0)i.bufferSubData(c,0,h);else{u.sort((p,_)=>p.start-_.start);let f=0;for(let p=1;p<u.length;p++){const _=u[f],y=u[p];y.start<=_.start+_.count+1?_.count=Math.max(_.count,y.start+y.count-_.start):(++f,u[f]=y)}u.length=f+1;for(let p=0,_=u.length;p<_;p++){const y=u[p];i.bufferSubData(c,y.start*h.BYTES_PER_ELEMENT,h,y.start,y.count)}l.clearUpdateRanges()}l.onUploadCallback()}function r(o){return o.isInterleavedBufferAttribute&&(o=o.data),e.get(o)}function s(o){o.isInterleavedBufferAttribute&&(o=o.data);const l=e.get(o);l&&(i.deleteBuffer(l.buffer),e.delete(o))}function a(o,l){if(o.isInterleavedBufferAttribute&&(o=o.data),o.isGLBufferAttribute){const h=e.get(o);(!h||h.version<o.version)&&e.set(o,{buffer:o.buffer,type:o.type,bytesPerElement:o.elementSize,version:o.version});return}const c=e.get(o);if(c===void 0)e.set(o,t(o,l));else if(c.version<o.version){if(c.size!==o.array.byteLength)throw new Error("THREE.WebGLAttributes: The size of the buffer attribute's array buffer does not match the original size. Resizing buffer attributes is not supported.");n(c.buffer,o,l),c.version=o.version}}return{get:r,remove:s,update:a}}var Pm=`#ifdef USE_ALPHAHASH
	if ( diffuseColor.a < getAlphaHashThreshold( vPosition ) ) discard;
#endif`,Im=`#ifdef USE_ALPHAHASH
	const float ALPHA_HASH_SCALE = 0.05;
	float hash2D( vec2 value ) {
		return fract( 1.0e4 * sin( 17.0 * value.x + 0.1 * value.y ) * ( 0.1 + abs( sin( 13.0 * value.y + value.x ) ) ) );
	}
	float hash3D( vec3 value ) {
		return hash2D( vec2( hash2D( value.xy ), value.z ) );
	}
	float getAlphaHashThreshold( vec3 position ) {
		float maxDeriv = max(
			length( dFdx( position.xyz ) ),
			length( dFdy( position.xyz ) )
		);
		float pixScale = 1.0 / ( ALPHA_HASH_SCALE * maxDeriv );
		vec2 pixScales = vec2(
			exp2( floor( log2( pixScale ) ) ),
			exp2( ceil( log2( pixScale ) ) )
		);
		vec2 alpha = vec2(
			hash3D( floor( pixScales.x * position.xyz ) ),
			hash3D( floor( pixScales.y * position.xyz ) )
		);
		float lerpFactor = fract( log2( pixScale ) );
		float x = ( 1.0 - lerpFactor ) * alpha.x + lerpFactor * alpha.y;
		float a = min( lerpFactor, 1.0 - lerpFactor );
		vec3 cases = vec3(
			x * x / ( 2.0 * a * ( 1.0 - a ) ),
			( x - 0.5 * a ) / ( 1.0 - a ),
			1.0 - ( ( 1.0 - x ) * ( 1.0 - x ) / ( 2.0 * a * ( 1.0 - a ) ) )
		);
		float threshold = ( x < ( 1.0 - a ) )
			? ( ( x < a ) ? cases.x : cases.y )
			: cases.z;
		return clamp( threshold , 1.0e-6, 1.0 );
	}
#endif`,Lm=`#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, vAlphaMapUv ).g;
#endif`,Dm=`#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,Nm=`#ifdef USE_ALPHATEST
	#ifdef ALPHA_TO_COVERAGE
	diffuseColor.a = smoothstep( alphaTest, alphaTest + fwidth( diffuseColor.a ), diffuseColor.a );
	if ( diffuseColor.a == 0.0 ) discard;
	#else
	if ( diffuseColor.a < alphaTest ) discard;
	#endif
#endif`,Um=`#ifdef USE_ALPHATEST
	uniform float alphaTest;
#endif`,Fm=`#ifdef USE_AOMAP
	float ambientOcclusion = ( texture2D( aoMap, vAoMapUv ).r - 1.0 ) * aoMapIntensity + 1.0;
	reflectedLight.indirectDiffuse *= ambientOcclusion;
	#if defined( USE_CLEARCOAT ) 
		clearcoatSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_SHEEN ) 
		sheenSpecularIndirect *= ambientOcclusion;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD )
		float dotNV = saturate( dot( geometryNormal, geometryViewDir ) );
		reflectedLight.indirectSpecular *= computeSpecularOcclusion( dotNV, ambientOcclusion, material.roughness );
	#endif
#endif`,Om=`#ifdef USE_AOMAP
	uniform sampler2D aoMap;
	uniform float aoMapIntensity;
#endif`,Bm=`#ifdef USE_BATCHING
	#if ! defined( GL_ANGLE_multi_draw )
	#define gl_DrawID _gl_DrawID
	uniform int _gl_DrawID;
	#endif
	uniform highp sampler2D batchingTexture;
	uniform highp usampler2D batchingIdTexture;
	mat4 getBatchingMatrix( const in float i ) {
		int size = textureSize( batchingTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( batchingTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( batchingTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( batchingTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( batchingTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
	float getIndirectIndex( const in int i ) {
		int size = textureSize( batchingIdTexture, 0 ).x;
		int x = i % size;
		int y = i / size;
		return float( texelFetch( batchingIdTexture, ivec2( x, y ), 0 ).r );
	}
#endif
#ifdef USE_BATCHING_COLOR
	uniform sampler2D batchingColorTexture;
	vec3 getBatchingColor( const in float i ) {
		int size = textureSize( batchingColorTexture, 0 ).x;
		int j = int( i );
		int x = j % size;
		int y = j / size;
		return texelFetch( batchingColorTexture, ivec2( x, y ), 0 ).rgb;
	}
#endif`,zm=`#ifdef USE_BATCHING
	mat4 batchingMatrix = getBatchingMatrix( getIndirectIndex( gl_DrawID ) );
#endif`,km=`vec3 transformed = vec3( position );
#ifdef USE_ALPHAHASH
	vPosition = vec3( position );
#endif`,Hm=`vec3 objectNormal = vec3( normal );
#ifdef USE_TANGENT
	vec3 objectTangent = vec3( tangent.xyz );
#endif`,Gm=`float G_BlinnPhong_Implicit( ) {
	return 0.25;
}
float D_BlinnPhong( const in float shininess, const in float dotNH ) {
	return RECIPROCAL_PI * ( shininess * 0.5 + 1.0 ) * pow( dotNH, shininess );
}
vec3 BRDF_BlinnPhong( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in vec3 specularColor, const in float shininess ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( specularColor, 1.0, dotVH );
	float G = G_BlinnPhong_Implicit( );
	float D = D_BlinnPhong( shininess, dotNH );
	return F * ( G * D );
} // validated`,Vm=`#ifdef USE_IRIDESCENCE
	const mat3 XYZ_TO_REC709 = mat3(
		 3.2404542, -0.9692660,  0.0556434,
		-1.5371385,  1.8760108, -0.2040259,
		-0.4985314,  0.0415560,  1.0572252
	);
	vec3 Fresnel0ToIor( vec3 fresnel0 ) {
		vec3 sqrtF0 = sqrt( fresnel0 );
		return ( vec3( 1.0 ) + sqrtF0 ) / ( vec3( 1.0 ) - sqrtF0 );
	}
	vec3 IorToFresnel0( vec3 transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - vec3( incidentIor ) ) / ( transmittedIor + vec3( incidentIor ) ) );
	}
	float IorToFresnel0( float transmittedIor, float incidentIor ) {
		return pow2( ( transmittedIor - incidentIor ) / ( transmittedIor + incidentIor ));
	}
	vec3 evalSensitivity( float OPD, vec3 shift ) {
		float phase = 2.0 * PI * OPD * 1.0e-9;
		vec3 val = vec3( 5.4856e-13, 4.4201e-13, 5.2481e-13 );
		vec3 pos = vec3( 1.6810e+06, 1.7953e+06, 2.2084e+06 );
		vec3 var = vec3( 4.3278e+09, 9.3046e+09, 6.6121e+09 );
		vec3 xyz = val * sqrt( 2.0 * PI * var ) * cos( pos * phase + shift ) * exp( - pow2( phase ) * var );
		xyz.x += 9.7470e-14 * sqrt( 2.0 * PI * 4.5282e+09 ) * cos( 2.2399e+06 * phase + shift[ 0 ] ) * exp( - 4.5282e+09 * pow2( phase ) );
		xyz /= 1.0685e-7;
		vec3 rgb = XYZ_TO_REC709 * xyz;
		return rgb;
	}
	vec3 evalIridescence( float outsideIOR, float eta2, float cosTheta1, float thinFilmThickness, vec3 baseF0 ) {
		vec3 I;
		float iridescenceIOR = mix( outsideIOR, eta2, smoothstep( 0.0, 0.03, thinFilmThickness ) );
		float sinTheta2Sq = pow2( outsideIOR / iridescenceIOR ) * ( 1.0 - pow2( cosTheta1 ) );
		float cosTheta2Sq = 1.0 - sinTheta2Sq;
		if ( cosTheta2Sq < 0.0 ) {
			return vec3( 1.0 );
		}
		float cosTheta2 = sqrt( cosTheta2Sq );
		float R0 = IorToFresnel0( iridescenceIOR, outsideIOR );
		float R12 = F_Schlick( R0, 1.0, cosTheta1 );
		float T121 = 1.0 - R12;
		float phi12 = 0.0;
		if ( iridescenceIOR < outsideIOR ) phi12 = PI;
		float phi21 = PI - phi12;
		vec3 baseIOR = Fresnel0ToIor( clamp( baseF0, 0.0, 0.9999 ) );		vec3 R1 = IorToFresnel0( baseIOR, iridescenceIOR );
		vec3 R23 = F_Schlick( R1, 1.0, cosTheta2 );
		vec3 phi23 = vec3( 0.0 );
		if ( baseIOR[ 0 ] < iridescenceIOR ) phi23[ 0 ] = PI;
		if ( baseIOR[ 1 ] < iridescenceIOR ) phi23[ 1 ] = PI;
		if ( baseIOR[ 2 ] < iridescenceIOR ) phi23[ 2 ] = PI;
		float OPD = 2.0 * iridescenceIOR * thinFilmThickness * cosTheta2;
		vec3 phi = vec3( phi21 ) + phi23;
		vec3 R123 = clamp( R12 * R23, 1e-5, 0.9999 );
		vec3 r123 = sqrt( R123 );
		vec3 Rs = pow2( T121 ) * R23 / ( vec3( 1.0 ) - R123 );
		vec3 C0 = R12 + Rs;
		I = C0;
		vec3 Cm = Rs - T121;
		for ( int m = 1; m <= 2; ++ m ) {
			Cm *= r123;
			vec3 Sm = 2.0 * evalSensitivity( float( m ) * OPD, float( m ) * phi );
			I += Cm * Sm;
		}
		return max( I, vec3( 0.0 ) );
	}
#endif`,Wm=`#ifdef USE_BUMPMAP
	uniform sampler2D bumpMap;
	uniform float bumpScale;
	vec2 dHdxy_fwd() {
		vec2 dSTdx = dFdx( vBumpMapUv );
		vec2 dSTdy = dFdy( vBumpMapUv );
		float Hll = bumpScale * texture2D( bumpMap, vBumpMapUv ).x;
		float dBx = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdx ).x - Hll;
		float dBy = bumpScale * texture2D( bumpMap, vBumpMapUv + dSTdy ).x - Hll;
		return vec2( dBx, dBy );
	}
	vec3 perturbNormalArb( vec3 surf_pos, vec3 surf_norm, vec2 dHdxy, float faceDirection ) {
		vec3 vSigmaX = normalize( dFdx( surf_pos.xyz ) );
		vec3 vSigmaY = normalize( dFdy( surf_pos.xyz ) );
		vec3 vN = surf_norm;
		vec3 R1 = cross( vSigmaY, vN );
		vec3 R2 = cross( vN, vSigmaX );
		float fDet = dot( vSigmaX, R1 ) * faceDirection;
		vec3 vGrad = sign( fDet ) * ( dHdxy.x * R1 + dHdxy.y * R2 );
		return normalize( abs( fDet ) * surf_norm - vGrad );
	}
#endif`,Xm=`#if NUM_CLIPPING_PLANES > 0
	vec4 plane;
	#ifdef ALPHA_TO_COVERAGE
		float distanceToPlane, distanceGradient;
		float clipOpacity = 1.0;
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
			distanceGradient = fwidth( distanceToPlane ) / 2.0;
			clipOpacity *= smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			if ( clipOpacity == 0.0 ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			float unionClipOpacity = 1.0;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				distanceToPlane = - dot( vClipPosition, plane.xyz ) + plane.w;
				distanceGradient = fwidth( distanceToPlane ) / 2.0;
				unionClipOpacity *= 1.0 - smoothstep( - distanceGradient, distanceGradient, distanceToPlane );
			}
			#pragma unroll_loop_end
			clipOpacity *= 1.0 - unionClipOpacity;
		#endif
		diffuseColor.a *= clipOpacity;
		if ( diffuseColor.a == 0.0 ) discard;
	#else
		#pragma unroll_loop_start
		for ( int i = 0; i < UNION_CLIPPING_PLANES; i ++ ) {
			plane = clippingPlanes[ i ];
			if ( dot( vClipPosition, plane.xyz ) > plane.w ) discard;
		}
		#pragma unroll_loop_end
		#if UNION_CLIPPING_PLANES < NUM_CLIPPING_PLANES
			bool clipped = true;
			#pragma unroll_loop_start
			for ( int i = UNION_CLIPPING_PLANES; i < NUM_CLIPPING_PLANES; i ++ ) {
				plane = clippingPlanes[ i ];
				clipped = ( dot( vClipPosition, plane.xyz ) > plane.w ) && clipped;
			}
			#pragma unroll_loop_end
			if ( clipped ) discard;
		#endif
	#endif
#endif`,jm=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
	uniform vec4 clippingPlanes[ NUM_CLIPPING_PLANES ];
#endif`,qm=`#if NUM_CLIPPING_PLANES > 0
	varying vec3 vClipPosition;
#endif`,Ym=`#if NUM_CLIPPING_PLANES > 0
	vClipPosition = - mvPosition.xyz;
#endif`,Km=`#if defined( USE_COLOR_ALPHA )
	diffuseColor *= vColor;
#elif defined( USE_COLOR )
	diffuseColor.rgb *= vColor;
#endif`,$m=`#if defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#elif defined( USE_COLOR )
	varying vec3 vColor;
#endif`,Zm=`#if defined( USE_COLOR_ALPHA )
	varying vec4 vColor;
#elif defined( USE_COLOR ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	varying vec3 vColor;
#endif`,Jm=`#if defined( USE_COLOR_ALPHA )
	vColor = vec4( 1.0 );
#elif defined( USE_COLOR ) || defined( USE_INSTANCING_COLOR ) || defined( USE_BATCHING_COLOR )
	vColor = vec3( 1.0 );
#endif
#ifdef USE_COLOR
	vColor *= color;
#endif
#ifdef USE_INSTANCING_COLOR
	vColor.xyz *= instanceColor.xyz;
#endif
#ifdef USE_BATCHING_COLOR
	vec3 batchingColor = getBatchingColor( getIndirectIndex( gl_DrawID ) );
	vColor.xyz *= batchingColor.xyz;
#endif`,Qm=`#define PI 3.141592653589793
#define PI2 6.283185307179586
#define PI_HALF 1.5707963267948966
#define RECIPROCAL_PI 0.3183098861837907
#define RECIPROCAL_PI2 0.15915494309189535
#define EPSILON 1e-6
#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
#define whiteComplement( a ) ( 1.0 - saturate( a ) )
float pow2( const in float x ) { return x*x; }
vec3 pow2( const in vec3 x ) { return x*x; }
float pow3( const in float x ) { return x*x*x; }
float pow4( const in float x ) { float x2 = x*x; return x2*x2; }
float max3( const in vec3 v ) { return max( max( v.x, v.y ), v.z ); }
float average( const in vec3 v ) { return dot( v, vec3( 0.3333333 ) ); }
highp float rand( const in vec2 uv ) {
	const highp float a = 12.9898, b = 78.233, c = 43758.5453;
	highp float dt = dot( uv.xy, vec2( a,b ) ), sn = mod( dt, PI );
	return fract( sin( sn ) * c );
}
#ifdef HIGH_PRECISION
	float precisionSafeLength( vec3 v ) { return length( v ); }
#else
	float precisionSafeLength( vec3 v ) {
		float maxComponent = max3( abs( v ) );
		return length( v / maxComponent ) * maxComponent;
	}
#endif
struct IncidentLight {
	vec3 color;
	vec3 direction;
	bool visible;
};
struct ReflectedLight {
	vec3 directDiffuse;
	vec3 directSpecular;
	vec3 indirectDiffuse;
	vec3 indirectSpecular;
};
#ifdef USE_ALPHAHASH
	varying vec3 vPosition;
#endif
vec3 transformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( matrix * vec4( dir, 0.0 ) ).xyz );
}
vec3 inverseTransformDirection( in vec3 dir, in mat4 matrix ) {
	return normalize( ( vec4( dir, 0.0 ) * matrix ).xyz );
}
mat3 transposeMat3( const in mat3 m ) {
	mat3 tmp;
	tmp[ 0 ] = vec3( m[ 0 ].x, m[ 1 ].x, m[ 2 ].x );
	tmp[ 1 ] = vec3( m[ 0 ].y, m[ 1 ].y, m[ 2 ].y );
	tmp[ 2 ] = vec3( m[ 0 ].z, m[ 1 ].z, m[ 2 ].z );
	return tmp;
}
bool isPerspectiveMatrix( mat4 m ) {
	return m[ 2 ][ 3 ] == - 1.0;
}
vec2 equirectUv( in vec3 dir ) {
	float u = atan( dir.z, dir.x ) * RECIPROCAL_PI2 + 0.5;
	float v = asin( clamp( dir.y, - 1.0, 1.0 ) ) * RECIPROCAL_PI + 0.5;
	return vec2( u, v );
}
vec3 BRDF_Lambert( const in vec3 diffuseColor ) {
	return RECIPROCAL_PI * diffuseColor;
}
vec3 F_Schlick( const in vec3 f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
}
float F_Schlick( const in float f0, const in float f90, const in float dotVH ) {
	float fresnel = exp2( ( - 5.55473 * dotVH - 6.98316 ) * dotVH );
	return f0 * ( 1.0 - fresnel ) + ( f90 * fresnel );
} // validated`,eg=`#ifdef ENVMAP_TYPE_CUBE_UV
	#define cubeUV_minMipLevel 4.0
	#define cubeUV_minTileSize 16.0
	float getFace( vec3 direction ) {
		vec3 absDirection = abs( direction );
		float face = - 1.0;
		if ( absDirection.x > absDirection.z ) {
			if ( absDirection.x > absDirection.y )
				face = direction.x > 0.0 ? 0.0 : 3.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		} else {
			if ( absDirection.z > absDirection.y )
				face = direction.z > 0.0 ? 2.0 : 5.0;
			else
				face = direction.y > 0.0 ? 1.0 : 4.0;
		}
		return face;
	}
	vec2 getUV( vec3 direction, float face ) {
		vec2 uv;
		if ( face == 0.0 ) {
			uv = vec2( direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 1.0 ) {
			uv = vec2( - direction.x, - direction.z ) / abs( direction.y );
		} else if ( face == 2.0 ) {
			uv = vec2( - direction.x, direction.y ) / abs( direction.z );
		} else if ( face == 3.0 ) {
			uv = vec2( - direction.z, direction.y ) / abs( direction.x );
		} else if ( face == 4.0 ) {
			uv = vec2( - direction.x, direction.z ) / abs( direction.y );
		} else {
			uv = vec2( direction.x, direction.y ) / abs( direction.z );
		}
		return 0.5 * ( uv + 1.0 );
	}
	vec3 bilinearCubeUV( sampler2D envMap, vec3 direction, float mipInt ) {
		float face = getFace( direction );
		float filterInt = max( cubeUV_minMipLevel - mipInt, 0.0 );
		mipInt = max( mipInt, cubeUV_minMipLevel );
		float faceSize = exp2( mipInt );
		highp vec2 uv = getUV( direction, face ) * ( faceSize - 2.0 ) + 1.0;
		if ( face > 2.0 ) {
			uv.y += faceSize;
			face -= 3.0;
		}
		uv.x += face * faceSize;
		uv.x += filterInt * 3.0 * cubeUV_minTileSize;
		uv.y += 4.0 * ( exp2( CUBEUV_MAX_MIP ) - faceSize );
		uv.x *= CUBEUV_TEXEL_WIDTH;
		uv.y *= CUBEUV_TEXEL_HEIGHT;
		#ifdef texture2DGradEXT
			return texture2DGradEXT( envMap, uv, vec2( 0.0 ), vec2( 0.0 ) ).rgb;
		#else
			return texture2D( envMap, uv ).rgb;
		#endif
	}
	#define cubeUV_r0 1.0
	#define cubeUV_m0 - 2.0
	#define cubeUV_r1 0.8
	#define cubeUV_m1 - 1.0
	#define cubeUV_r4 0.4
	#define cubeUV_m4 2.0
	#define cubeUV_r5 0.305
	#define cubeUV_m5 3.0
	#define cubeUV_r6 0.21
	#define cubeUV_m6 4.0
	float roughnessToMip( float roughness ) {
		float mip = 0.0;
		if ( roughness >= cubeUV_r1 ) {
			mip = ( cubeUV_r0 - roughness ) * ( cubeUV_m1 - cubeUV_m0 ) / ( cubeUV_r0 - cubeUV_r1 ) + cubeUV_m0;
		} else if ( roughness >= cubeUV_r4 ) {
			mip = ( cubeUV_r1 - roughness ) * ( cubeUV_m4 - cubeUV_m1 ) / ( cubeUV_r1 - cubeUV_r4 ) + cubeUV_m1;
		} else if ( roughness >= cubeUV_r5 ) {
			mip = ( cubeUV_r4 - roughness ) * ( cubeUV_m5 - cubeUV_m4 ) / ( cubeUV_r4 - cubeUV_r5 ) + cubeUV_m4;
		} else if ( roughness >= cubeUV_r6 ) {
			mip = ( cubeUV_r5 - roughness ) * ( cubeUV_m6 - cubeUV_m5 ) / ( cubeUV_r5 - cubeUV_r6 ) + cubeUV_m5;
		} else {
			mip = - 2.0 * log2( 1.16 * roughness );		}
		return mip;
	}
	vec4 textureCubeUV( sampler2D envMap, vec3 sampleDir, float roughness ) {
		float mip = clamp( roughnessToMip( roughness ), cubeUV_m0, CUBEUV_MAX_MIP );
		float mipF = fract( mip );
		float mipInt = floor( mip );
		vec3 color0 = bilinearCubeUV( envMap, sampleDir, mipInt );
		if ( mipF == 0.0 ) {
			return vec4( color0, 1.0 );
		} else {
			vec3 color1 = bilinearCubeUV( envMap, sampleDir, mipInt + 1.0 );
			return vec4( mix( color0, color1, mipF ), 1.0 );
		}
	}
#endif`,tg=`vec3 transformedNormal = objectNormal;
#ifdef USE_TANGENT
	vec3 transformedTangent = objectTangent;
#endif
#ifdef USE_BATCHING
	mat3 bm = mat3( batchingMatrix );
	transformedNormal /= vec3( dot( bm[ 0 ], bm[ 0 ] ), dot( bm[ 1 ], bm[ 1 ] ), dot( bm[ 2 ], bm[ 2 ] ) );
	transformedNormal = bm * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = bm * transformedTangent;
	#endif
#endif
#ifdef USE_INSTANCING
	mat3 im = mat3( instanceMatrix );
	transformedNormal /= vec3( dot( im[ 0 ], im[ 0 ] ), dot( im[ 1 ], im[ 1 ] ), dot( im[ 2 ], im[ 2 ] ) );
	transformedNormal = im * transformedNormal;
	#ifdef USE_TANGENT
		transformedTangent = im * transformedTangent;
	#endif
#endif
transformedNormal = normalMatrix * transformedNormal;
#ifdef FLIP_SIDED
	transformedNormal = - transformedNormal;
#endif
#ifdef USE_TANGENT
	transformedTangent = ( modelViewMatrix * vec4( transformedTangent, 0.0 ) ).xyz;
	#ifdef FLIP_SIDED
		transformedTangent = - transformedTangent;
	#endif
#endif`,ng=`#ifdef USE_DISPLACEMENTMAP
	uniform sampler2D displacementMap;
	uniform float displacementScale;
	uniform float displacementBias;
#endif`,ig=`#ifdef USE_DISPLACEMENTMAP
	transformed += normalize( objectNormal ) * ( texture2D( displacementMap, vDisplacementMapUv ).x * displacementScale + displacementBias );
#endif`,rg=`#ifdef USE_EMISSIVEMAP
	vec4 emissiveColor = texture2D( emissiveMap, vEmissiveMapUv );
	#ifdef DECODE_VIDEO_TEXTURE_EMISSIVE
		emissiveColor = sRGBTransferEOTF( emissiveColor );
	#endif
	totalEmissiveRadiance *= emissiveColor.rgb;
#endif`,sg=`#ifdef USE_EMISSIVEMAP
	uniform sampler2D emissiveMap;
#endif`,ag="gl_FragColor = linearToOutputTexel( gl_FragColor );",og=`vec4 LinearTransferOETF( in vec4 value ) {
	return value;
}
vec4 sRGBTransferEOTF( in vec4 value ) {
	return vec4( mix( pow( value.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), value.rgb * 0.0773993808, vec3( lessThanEqual( value.rgb, vec3( 0.04045 ) ) ) ), value.a );
}
vec4 sRGBTransferOETF( in vec4 value ) {
	return vec4( mix( pow( value.rgb, vec3( 0.41666 ) ) * 1.055 - vec3( 0.055 ), value.rgb * 12.92, vec3( lessThanEqual( value.rgb, vec3( 0.0031308 ) ) ) ), value.a );
}`,lg=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vec3 cameraToFrag;
		if ( isOrthographic ) {
			cameraToFrag = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToFrag = normalize( vWorldPosition - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vec3 reflectVec = reflect( cameraToFrag, worldNormal );
		#else
			vec3 reflectVec = refract( cameraToFrag, worldNormal, refractionRatio );
		#endif
	#else
		vec3 reflectVec = vReflect;
	#endif
	#ifdef ENVMAP_TYPE_CUBE
		vec4 envColor = textureCube( envMap, envMapRotation * vec3( flipEnvMap * reflectVec.x, reflectVec.yz ) );
	#else
		vec4 envColor = vec4( 0.0 );
	#endif
	#ifdef ENVMAP_BLENDING_MULTIPLY
		outgoingLight = mix( outgoingLight, outgoingLight * envColor.xyz, specularStrength * reflectivity );
	#elif defined( ENVMAP_BLENDING_MIX )
		outgoingLight = mix( outgoingLight, envColor.xyz, specularStrength * reflectivity );
	#elif defined( ENVMAP_BLENDING_ADD )
		outgoingLight += envColor.xyz * specularStrength * reflectivity;
	#endif
#endif`,cg=`#ifdef USE_ENVMAP
	uniform float envMapIntensity;
	uniform float flipEnvMap;
	uniform mat3 envMapRotation;
	#ifdef ENVMAP_TYPE_CUBE
		uniform samplerCube envMap;
	#else
		uniform sampler2D envMap;
	#endif
	
#endif`,dg=`#ifdef USE_ENVMAP
	uniform float reflectivity;
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		varying vec3 vWorldPosition;
		uniform float refractionRatio;
	#else
		varying vec3 vReflect;
	#endif
#endif`,ug=`#ifdef USE_ENVMAP
	#if defined( USE_BUMPMAP ) || defined( USE_NORMALMAP ) || defined( PHONG ) || defined( LAMBERT )
		#define ENV_WORLDPOS
	#endif
	#ifdef ENV_WORLDPOS
		
		varying vec3 vWorldPosition;
	#else
		varying vec3 vReflect;
		uniform float refractionRatio;
	#endif
#endif`,hg=`#ifdef USE_ENVMAP
	#ifdef ENV_WORLDPOS
		vWorldPosition = worldPosition.xyz;
	#else
		vec3 cameraToVertex;
		if ( isOrthographic ) {
			cameraToVertex = normalize( vec3( - viewMatrix[ 0 ][ 2 ], - viewMatrix[ 1 ][ 2 ], - viewMatrix[ 2 ][ 2 ] ) );
		} else {
			cameraToVertex = normalize( worldPosition.xyz - cameraPosition );
		}
		vec3 worldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
		#ifdef ENVMAP_MODE_REFLECTION
			vReflect = reflect( cameraToVertex, worldNormal );
		#else
			vReflect = refract( cameraToVertex, worldNormal, refractionRatio );
		#endif
	#endif
#endif`,fg=`#ifdef USE_FOG
	vFogDepth = - mvPosition.z;
#endif`,pg=`#ifdef USE_FOG
	varying float vFogDepth;
#endif`,mg=`#ifdef USE_FOG
	#ifdef FOG_EXP2
		float fogFactor = 1.0 - exp( - fogDensity * fogDensity * vFogDepth * vFogDepth );
	#else
		float fogFactor = smoothstep( fogNear, fogFar, vFogDepth );
	#endif
	gl_FragColor.rgb = mix( gl_FragColor.rgb, fogColor, fogFactor );
#endif`,gg=`#ifdef USE_FOG
	uniform vec3 fogColor;
	varying float vFogDepth;
	#ifdef FOG_EXP2
		uniform float fogDensity;
	#else
		uniform float fogNear;
		uniform float fogFar;
	#endif
#endif`,_g=`#ifdef USE_GRADIENTMAP
	uniform sampler2D gradientMap;
#endif
vec3 getGradientIrradiance( vec3 normal, vec3 lightDirection ) {
	float dotNL = dot( normal, lightDirection );
	vec2 coord = vec2( dotNL * 0.5 + 0.5, 0.0 );
	#ifdef USE_GRADIENTMAP
		return vec3( texture2D( gradientMap, coord ).r );
	#else
		vec2 fw = fwidth( coord ) * 0.5;
		return mix( vec3( 0.7 ), vec3( 1.0 ), smoothstep( 0.7 - fw.x, 0.7 + fw.x, coord.x ) );
	#endif
}`,yg=`#ifdef USE_LIGHTMAP
	uniform sampler2D lightMap;
	uniform float lightMapIntensity;
#endif`,xg=`LambertMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularStrength = specularStrength;`,vg=`varying vec3 vViewPosition;
struct LambertMaterial {
	vec3 diffuseColor;
	float specularStrength;
};
void RE_Direct_Lambert( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Lambert( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in LambertMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Lambert
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Lambert`,Mg=`uniform bool receiveShadow;
uniform vec3 ambientLightColor;
#if defined( USE_LIGHT_PROBES )
	uniform vec3 lightProbe[ 9 ];
#endif
vec3 shGetIrradianceAt( in vec3 normal, in vec3 shCoefficients[ 9 ] ) {
	float x = normal.x, y = normal.y, z = normal.z;
	vec3 result = shCoefficients[ 0 ] * 0.886227;
	result += shCoefficients[ 1 ] * 2.0 * 0.511664 * y;
	result += shCoefficients[ 2 ] * 2.0 * 0.511664 * z;
	result += shCoefficients[ 3 ] * 2.0 * 0.511664 * x;
	result += shCoefficients[ 4 ] * 2.0 * 0.429043 * x * y;
	result += shCoefficients[ 5 ] * 2.0 * 0.429043 * y * z;
	result += shCoefficients[ 6 ] * ( 0.743125 * z * z - 0.247708 );
	result += shCoefficients[ 7 ] * 2.0 * 0.429043 * x * z;
	result += shCoefficients[ 8 ] * 0.429043 * ( x * x - y * y );
	return result;
}
vec3 getLightProbeIrradiance( const in vec3 lightProbe[ 9 ], const in vec3 normal ) {
	vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
	vec3 irradiance = shGetIrradianceAt( worldNormal, lightProbe );
	return irradiance;
}
vec3 getAmbientLightIrradiance( const in vec3 ambientLightColor ) {
	vec3 irradiance = ambientLightColor;
	return irradiance;
}
float getDistanceAttenuation( const in float lightDistance, const in float cutoffDistance, const in float decayExponent ) {
	float distanceFalloff = 1.0 / max( pow( lightDistance, decayExponent ), 0.01 );
	if ( cutoffDistance > 0.0 ) {
		distanceFalloff *= pow2( saturate( 1.0 - pow4( lightDistance / cutoffDistance ) ) );
	}
	return distanceFalloff;
}
float getSpotAttenuation( const in float coneCosine, const in float penumbraCosine, const in float angleCosine ) {
	return smoothstep( coneCosine, penumbraCosine, angleCosine );
}
#if NUM_DIR_LIGHTS > 0
	struct DirectionalLight {
		vec3 direction;
		vec3 color;
	};
	uniform DirectionalLight directionalLights[ NUM_DIR_LIGHTS ];
	void getDirectionalLightInfo( const in DirectionalLight directionalLight, out IncidentLight light ) {
		light.color = directionalLight.color;
		light.direction = directionalLight.direction;
		light.visible = true;
	}
#endif
#if NUM_POINT_LIGHTS > 0
	struct PointLight {
		vec3 position;
		vec3 color;
		float distance;
		float decay;
	};
	uniform PointLight pointLights[ NUM_POINT_LIGHTS ];
	void getPointLightInfo( const in PointLight pointLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = pointLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float lightDistance = length( lVector );
		light.color = pointLight.color;
		light.color *= getDistanceAttenuation( lightDistance, pointLight.distance, pointLight.decay );
		light.visible = ( light.color != vec3( 0.0 ) );
	}
#endif
#if NUM_SPOT_LIGHTS > 0
	struct SpotLight {
		vec3 position;
		vec3 direction;
		vec3 color;
		float distance;
		float decay;
		float coneCos;
		float penumbraCos;
	};
	uniform SpotLight spotLights[ NUM_SPOT_LIGHTS ];
	void getSpotLightInfo( const in SpotLight spotLight, const in vec3 geometryPosition, out IncidentLight light ) {
		vec3 lVector = spotLight.position - geometryPosition;
		light.direction = normalize( lVector );
		float angleCos = dot( light.direction, spotLight.direction );
		float spotAttenuation = getSpotAttenuation( spotLight.coneCos, spotLight.penumbraCos, angleCos );
		if ( spotAttenuation > 0.0 ) {
			float lightDistance = length( lVector );
			light.color = spotLight.color * spotAttenuation;
			light.color *= getDistanceAttenuation( lightDistance, spotLight.distance, spotLight.decay );
			light.visible = ( light.color != vec3( 0.0 ) );
		} else {
			light.color = vec3( 0.0 );
			light.visible = false;
		}
	}
#endif
#if NUM_RECT_AREA_LIGHTS > 0
	struct RectAreaLight {
		vec3 color;
		vec3 position;
		vec3 halfWidth;
		vec3 halfHeight;
	};
	uniform sampler2D ltc_1;	uniform sampler2D ltc_2;
	uniform RectAreaLight rectAreaLights[ NUM_RECT_AREA_LIGHTS ];
#endif
#if NUM_HEMI_LIGHTS > 0
	struct HemisphereLight {
		vec3 direction;
		vec3 skyColor;
		vec3 groundColor;
	};
	uniform HemisphereLight hemisphereLights[ NUM_HEMI_LIGHTS ];
	vec3 getHemisphereLightIrradiance( const in HemisphereLight hemiLight, const in vec3 normal ) {
		float dotNL = dot( normal, hemiLight.direction );
		float hemiDiffuseWeight = 0.5 * dotNL + 0.5;
		vec3 irradiance = mix( hemiLight.groundColor, hemiLight.skyColor, hemiDiffuseWeight );
		return irradiance;
	}
#endif`,bg=`#ifdef USE_ENVMAP
	vec3 getIBLIrradiance( const in vec3 normal ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 worldNormal = inverseTransformDirection( normal, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * worldNormal, 1.0 );
			return PI * envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	vec3 getIBLRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness ) {
		#ifdef ENVMAP_TYPE_CUBE_UV
			vec3 reflectVec = reflect( - viewDir, normal );
			reflectVec = normalize( mix( reflectVec, normal, roughness * roughness) );
			reflectVec = inverseTransformDirection( reflectVec, viewMatrix );
			vec4 envMapColor = textureCubeUV( envMap, envMapRotation * reflectVec, roughness );
			return envMapColor.rgb * envMapIntensity;
		#else
			return vec3( 0.0 );
		#endif
	}
	#ifdef USE_ANISOTROPY
		vec3 getIBLAnisotropyRadiance( const in vec3 viewDir, const in vec3 normal, const in float roughness, const in vec3 bitangent, const in float anisotropy ) {
			#ifdef ENVMAP_TYPE_CUBE_UV
				vec3 bentNormal = cross( bitangent, viewDir );
				bentNormal = normalize( cross( bentNormal, bitangent ) );
				bentNormal = normalize( mix( bentNormal, normal, pow2( pow2( 1.0 - anisotropy * ( 1.0 - roughness ) ) ) ) );
				return getIBLRadiance( viewDir, bentNormal, roughness );
			#else
				return vec3( 0.0 );
			#endif
		}
	#endif
#endif`,Sg=`ToonMaterial material;
material.diffuseColor = diffuseColor.rgb;`,wg=`varying vec3 vViewPosition;
struct ToonMaterial {
	vec3 diffuseColor;
};
void RE_Direct_Toon( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	vec3 irradiance = getGradientIrradiance( geometryNormal, directLight.direction ) * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Toon( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in ToonMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_Toon
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Toon`,Eg=`BlinnPhongMaterial material;
material.diffuseColor = diffuseColor.rgb;
material.specularColor = specular;
material.specularShininess = shininess;
material.specularStrength = specularStrength;`,Tg=`varying vec3 vViewPosition;
struct BlinnPhongMaterial {
	vec3 diffuseColor;
	vec3 specularColor;
	float specularShininess;
	float specularStrength;
};
void RE_Direct_BlinnPhong( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
	reflectedLight.directSpecular += irradiance * BRDF_BlinnPhong( directLight.direction, geometryViewDir, geometryNormal, material.specularColor, material.specularShininess ) * material.specularStrength;
}
void RE_IndirectDiffuse_BlinnPhong( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in BlinnPhongMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
#define RE_Direct				RE_Direct_BlinnPhong
#define RE_IndirectDiffuse		RE_IndirectDiffuse_BlinnPhong`,Ag=`PhysicalMaterial material;
material.diffuseColor = diffuseColor.rgb * ( 1.0 - metalnessFactor );
vec3 dxy = max( abs( dFdx( nonPerturbedNormal ) ), abs( dFdy( nonPerturbedNormal ) ) );
float geometryRoughness = max( max( dxy.x, dxy.y ), dxy.z );
material.roughness = max( roughnessFactor, 0.0525 );material.roughness += geometryRoughness;
material.roughness = min( material.roughness, 1.0 );
#ifdef IOR
	material.ior = ior;
	#ifdef USE_SPECULAR
		float specularIntensityFactor = specularIntensity;
		vec3 specularColorFactor = specularColor;
		#ifdef USE_SPECULAR_COLORMAP
			specularColorFactor *= texture2D( specularColorMap, vSpecularColorMapUv ).rgb;
		#endif
		#ifdef USE_SPECULAR_INTENSITYMAP
			specularIntensityFactor *= texture2D( specularIntensityMap, vSpecularIntensityMapUv ).a;
		#endif
		material.specularF90 = mix( specularIntensityFactor, 1.0, metalnessFactor );
	#else
		float specularIntensityFactor = 1.0;
		vec3 specularColorFactor = vec3( 1.0 );
		material.specularF90 = 1.0;
	#endif
	material.specularColor = mix( min( pow2( ( material.ior - 1.0 ) / ( material.ior + 1.0 ) ) * specularColorFactor, vec3( 1.0 ) ) * specularIntensityFactor, diffuseColor.rgb, metalnessFactor );
#else
	material.specularColor = mix( vec3( 0.04 ), diffuseColor.rgb, metalnessFactor );
	material.specularF90 = 1.0;
#endif
#ifdef USE_CLEARCOAT
	material.clearcoat = clearcoat;
	material.clearcoatRoughness = clearcoatRoughness;
	material.clearcoatF0 = vec3( 0.04 );
	material.clearcoatF90 = 1.0;
	#ifdef USE_CLEARCOATMAP
		material.clearcoat *= texture2D( clearcoatMap, vClearcoatMapUv ).x;
	#endif
	#ifdef USE_CLEARCOAT_ROUGHNESSMAP
		material.clearcoatRoughness *= texture2D( clearcoatRoughnessMap, vClearcoatRoughnessMapUv ).y;
	#endif
	material.clearcoat = saturate( material.clearcoat );	material.clearcoatRoughness = max( material.clearcoatRoughness, 0.0525 );
	material.clearcoatRoughness += geometryRoughness;
	material.clearcoatRoughness = min( material.clearcoatRoughness, 1.0 );
#endif
#ifdef USE_DISPERSION
	material.dispersion = dispersion;
#endif
#ifdef USE_IRIDESCENCE
	material.iridescence = iridescence;
	material.iridescenceIOR = iridescenceIOR;
	#ifdef USE_IRIDESCENCEMAP
		material.iridescence *= texture2D( iridescenceMap, vIridescenceMapUv ).r;
	#endif
	#ifdef USE_IRIDESCENCE_THICKNESSMAP
		material.iridescenceThickness = (iridescenceThicknessMaximum - iridescenceThicknessMinimum) * texture2D( iridescenceThicknessMap, vIridescenceThicknessMapUv ).g + iridescenceThicknessMinimum;
	#else
		material.iridescenceThickness = iridescenceThicknessMaximum;
	#endif
#endif
#ifdef USE_SHEEN
	material.sheenColor = sheenColor;
	#ifdef USE_SHEEN_COLORMAP
		material.sheenColor *= texture2D( sheenColorMap, vSheenColorMapUv ).rgb;
	#endif
	material.sheenRoughness = clamp( sheenRoughness, 0.07, 1.0 );
	#ifdef USE_SHEEN_ROUGHNESSMAP
		material.sheenRoughness *= texture2D( sheenRoughnessMap, vSheenRoughnessMapUv ).a;
	#endif
#endif
#ifdef USE_ANISOTROPY
	#ifdef USE_ANISOTROPYMAP
		mat2 anisotropyMat = mat2( anisotropyVector.x, anisotropyVector.y, - anisotropyVector.y, anisotropyVector.x );
		vec3 anisotropyPolar = texture2D( anisotropyMap, vAnisotropyMapUv ).rgb;
		vec2 anisotropyV = anisotropyMat * normalize( 2.0 * anisotropyPolar.rg - vec2( 1.0 ) ) * anisotropyPolar.b;
	#else
		vec2 anisotropyV = anisotropyVector;
	#endif
	material.anisotropy = length( anisotropyV );
	if( material.anisotropy == 0.0 ) {
		anisotropyV = vec2( 1.0, 0.0 );
	} else {
		anisotropyV /= material.anisotropy;
		material.anisotropy = saturate( material.anisotropy );
	}
	material.alphaT = mix( pow2( material.roughness ), 1.0, pow2( material.anisotropy ) );
	material.anisotropyT = tbn[ 0 ] * anisotropyV.x + tbn[ 1 ] * anisotropyV.y;
	material.anisotropyB = tbn[ 1 ] * anisotropyV.x - tbn[ 0 ] * anisotropyV.y;
#endif`,Rg=`struct PhysicalMaterial {
	vec3 diffuseColor;
	float roughness;
	vec3 specularColor;
	float specularF90;
	float dispersion;
	#ifdef USE_CLEARCOAT
		float clearcoat;
		float clearcoatRoughness;
		vec3 clearcoatF0;
		float clearcoatF90;
	#endif
	#ifdef USE_IRIDESCENCE
		float iridescence;
		float iridescenceIOR;
		float iridescenceThickness;
		vec3 iridescenceFresnel;
		vec3 iridescenceF0;
	#endif
	#ifdef USE_SHEEN
		vec3 sheenColor;
		float sheenRoughness;
	#endif
	#ifdef IOR
		float ior;
	#endif
	#ifdef USE_TRANSMISSION
		float transmission;
		float transmissionAlpha;
		float thickness;
		float attenuationDistance;
		vec3 attenuationColor;
	#endif
	#ifdef USE_ANISOTROPY
		float anisotropy;
		float alphaT;
		vec3 anisotropyT;
		vec3 anisotropyB;
	#endif
};
vec3 clearcoatSpecularDirect = vec3( 0.0 );
vec3 clearcoatSpecularIndirect = vec3( 0.0 );
vec3 sheenSpecularDirect = vec3( 0.0 );
vec3 sheenSpecularIndirect = vec3(0.0 );
vec3 Schlick_to_F0( const in vec3 f, const in float f90, const in float dotVH ) {
    float x = clamp( 1.0 - dotVH, 0.0, 1.0 );
    float x2 = x * x;
    float x5 = clamp( x * x2 * x2, 0.0, 0.9999 );
    return ( f - vec3( f90 ) * x5 ) / ( 1.0 - x5 );
}
float V_GGX_SmithCorrelated( const in float alpha, const in float dotNL, const in float dotNV ) {
	float a2 = pow2( alpha );
	float gv = dotNL * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNV ) );
	float gl = dotNV * sqrt( a2 + ( 1.0 - a2 ) * pow2( dotNL ) );
	return 0.5 / max( gv + gl, EPSILON );
}
float D_GGX( const in float alpha, const in float dotNH ) {
	float a2 = pow2( alpha );
	float denom = pow2( dotNH ) * ( a2 - 1.0 ) + 1.0;
	return RECIPROCAL_PI * a2 / pow2( denom );
}
#ifdef USE_ANISOTROPY
	float V_GGX_SmithCorrelated_Anisotropic( const in float alphaT, const in float alphaB, const in float dotTV, const in float dotBV, const in float dotTL, const in float dotBL, const in float dotNV, const in float dotNL ) {
		float gv = dotNL * length( vec3( alphaT * dotTV, alphaB * dotBV, dotNV ) );
		float gl = dotNV * length( vec3( alphaT * dotTL, alphaB * dotBL, dotNL ) );
		float v = 0.5 / ( gv + gl );
		return saturate(v);
	}
	float D_GGX_Anisotropic( const in float alphaT, const in float alphaB, const in float dotNH, const in float dotTH, const in float dotBH ) {
		float a2 = alphaT * alphaB;
		highp vec3 v = vec3( alphaB * dotTH, alphaT * dotBH, a2 * dotNH );
		highp float v2 = dot( v, v );
		float w2 = a2 / v2;
		return RECIPROCAL_PI * a2 * pow2 ( w2 );
	}
#endif
#ifdef USE_CLEARCOAT
	vec3 BRDF_GGX_Clearcoat( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material) {
		vec3 f0 = material.clearcoatF0;
		float f90 = material.clearcoatF90;
		float roughness = material.clearcoatRoughness;
		float alpha = pow2( roughness );
		vec3 halfDir = normalize( lightDir + viewDir );
		float dotNL = saturate( dot( normal, lightDir ) );
		float dotNV = saturate( dot( normal, viewDir ) );
		float dotNH = saturate( dot( normal, halfDir ) );
		float dotVH = saturate( dot( viewDir, halfDir ) );
		vec3 F = F_Schlick( f0, f90, dotVH );
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
		return F * ( V * D );
	}
#endif
vec3 BRDF_GGX( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, const in PhysicalMaterial material ) {
	vec3 f0 = material.specularColor;
	float f90 = material.specularF90;
	float roughness = material.roughness;
	float alpha = pow2( roughness );
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float dotVH = saturate( dot( viewDir, halfDir ) );
	vec3 F = F_Schlick( f0, f90, dotVH );
	#ifdef USE_IRIDESCENCE
		F = mix( F, material.iridescenceFresnel, material.iridescence );
	#endif
	#ifdef USE_ANISOTROPY
		float dotTL = dot( material.anisotropyT, lightDir );
		float dotTV = dot( material.anisotropyT, viewDir );
		float dotTH = dot( material.anisotropyT, halfDir );
		float dotBL = dot( material.anisotropyB, lightDir );
		float dotBV = dot( material.anisotropyB, viewDir );
		float dotBH = dot( material.anisotropyB, halfDir );
		float V = V_GGX_SmithCorrelated_Anisotropic( material.alphaT, alpha, dotTV, dotBV, dotTL, dotBL, dotNV, dotNL );
		float D = D_GGX_Anisotropic( material.alphaT, alpha, dotNH, dotTH, dotBH );
	#else
		float V = V_GGX_SmithCorrelated( alpha, dotNL, dotNV );
		float D = D_GGX( alpha, dotNH );
	#endif
	return F * ( V * D );
}
vec2 LTC_Uv( const in vec3 N, const in vec3 V, const in float roughness ) {
	const float LUT_SIZE = 64.0;
	const float LUT_SCALE = ( LUT_SIZE - 1.0 ) / LUT_SIZE;
	const float LUT_BIAS = 0.5 / LUT_SIZE;
	float dotNV = saturate( dot( N, V ) );
	vec2 uv = vec2( roughness, sqrt( 1.0 - dotNV ) );
	uv = uv * LUT_SCALE + LUT_BIAS;
	return uv;
}
float LTC_ClippedSphereFormFactor( const in vec3 f ) {
	float l = length( f );
	return max( ( l * l + f.z ) / ( l + 1.0 ), 0.0 );
}
vec3 LTC_EdgeVectorFormFactor( const in vec3 v1, const in vec3 v2 ) {
	float x = dot( v1, v2 );
	float y = abs( x );
	float a = 0.8543985 + ( 0.4965155 + 0.0145206 * y ) * y;
	float b = 3.4175940 + ( 4.1616724 + y ) * y;
	float v = a / b;
	float theta_sintheta = ( x > 0.0 ) ? v : 0.5 * inversesqrt( max( 1.0 - x * x, 1e-7 ) ) - v;
	return cross( v1, v2 ) * theta_sintheta;
}
vec3 LTC_Evaluate( const in vec3 N, const in vec3 V, const in vec3 P, const in mat3 mInv, const in vec3 rectCoords[ 4 ] ) {
	vec3 v1 = rectCoords[ 1 ] - rectCoords[ 0 ];
	vec3 v2 = rectCoords[ 3 ] - rectCoords[ 0 ];
	vec3 lightNormal = cross( v1, v2 );
	if( dot( lightNormal, P - rectCoords[ 0 ] ) < 0.0 ) return vec3( 0.0 );
	vec3 T1, T2;
	T1 = normalize( V - N * dot( V, N ) );
	T2 = - cross( N, T1 );
	mat3 mat = mInv * transposeMat3( mat3( T1, T2, N ) );
	vec3 coords[ 4 ];
	coords[ 0 ] = mat * ( rectCoords[ 0 ] - P );
	coords[ 1 ] = mat * ( rectCoords[ 1 ] - P );
	coords[ 2 ] = mat * ( rectCoords[ 2 ] - P );
	coords[ 3 ] = mat * ( rectCoords[ 3 ] - P );
	coords[ 0 ] = normalize( coords[ 0 ] );
	coords[ 1 ] = normalize( coords[ 1 ] );
	coords[ 2 ] = normalize( coords[ 2 ] );
	coords[ 3 ] = normalize( coords[ 3 ] );
	vec3 vectorFormFactor = vec3( 0.0 );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 0 ], coords[ 1 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 1 ], coords[ 2 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 2 ], coords[ 3 ] );
	vectorFormFactor += LTC_EdgeVectorFormFactor( coords[ 3 ], coords[ 0 ] );
	float result = LTC_ClippedSphereFormFactor( vectorFormFactor );
	return vec3( result );
}
#if defined( USE_SHEEN )
float D_Charlie( float roughness, float dotNH ) {
	float alpha = pow2( roughness );
	float invAlpha = 1.0 / alpha;
	float cos2h = dotNH * dotNH;
	float sin2h = max( 1.0 - cos2h, 0.0078125 );
	return ( 2.0 + invAlpha ) * pow( sin2h, invAlpha * 0.5 ) / ( 2.0 * PI );
}
float V_Neubelt( float dotNV, float dotNL ) {
	return saturate( 1.0 / ( 4.0 * ( dotNL + dotNV - dotNL * dotNV ) ) );
}
vec3 BRDF_Sheen( const in vec3 lightDir, const in vec3 viewDir, const in vec3 normal, vec3 sheenColor, const in float sheenRoughness ) {
	vec3 halfDir = normalize( lightDir + viewDir );
	float dotNL = saturate( dot( normal, lightDir ) );
	float dotNV = saturate( dot( normal, viewDir ) );
	float dotNH = saturate( dot( normal, halfDir ) );
	float D = D_Charlie( sheenRoughness, dotNH );
	float V = V_Neubelt( dotNV, dotNL );
	return sheenColor * ( D * V );
}
#endif
float IBLSheenBRDF( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	float r2 = roughness * roughness;
	float a = roughness < 0.25 ? -339.2 * r2 + 161.4 * roughness - 25.9 : -8.48 * r2 + 14.3 * roughness - 9.95;
	float b = roughness < 0.25 ? 44.0 * r2 - 23.7 * roughness + 3.26 : 1.97 * r2 - 3.27 * roughness + 0.72;
	float DG = exp( a * dotNV + b ) + ( roughness < 0.25 ? 0.0 : 0.1 * ( roughness - 0.25 ) );
	return saturate( DG * RECIPROCAL_PI );
}
vec2 DFGApprox( const in vec3 normal, const in vec3 viewDir, const in float roughness ) {
	float dotNV = saturate( dot( normal, viewDir ) );
	const vec4 c0 = vec4( - 1, - 0.0275, - 0.572, 0.022 );
	const vec4 c1 = vec4( 1, 0.0425, 1.04, - 0.04 );
	vec4 r = roughness * c0 + c1;
	float a004 = min( r.x * r.x, exp2( - 9.28 * dotNV ) ) * r.x + r.y;
	vec2 fab = vec2( - 1.04, 1.04 ) * a004 + r.zw;
	return fab;
}
vec3 EnvironmentBRDF( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness ) {
	vec2 fab = DFGApprox( normal, viewDir, roughness );
	return specularColor * fab.x + specularF90 * fab.y;
}
#ifdef USE_IRIDESCENCE
void computeMultiscatteringIridescence( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float iridescence, const in vec3 iridescenceF0, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#else
void computeMultiscattering( const in vec3 normal, const in vec3 viewDir, const in vec3 specularColor, const in float specularF90, const in float roughness, inout vec3 singleScatter, inout vec3 multiScatter ) {
#endif
	vec2 fab = DFGApprox( normal, viewDir, roughness );
	#ifdef USE_IRIDESCENCE
		vec3 Fr = mix( specularColor, iridescenceF0, iridescence );
	#else
		vec3 Fr = specularColor;
	#endif
	vec3 FssEss = Fr * fab.x + specularF90 * fab.y;
	float Ess = fab.x + fab.y;
	float Ems = 1.0 - Ess;
	vec3 Favg = Fr + ( 1.0 - Fr ) * 0.047619;	vec3 Fms = FssEss * Favg / ( 1.0 - Ems * Favg );
	singleScatter += FssEss;
	multiScatter += Fms * Ems;
}
#if NUM_RECT_AREA_LIGHTS > 0
	void RE_Direct_RectArea_Physical( const in RectAreaLight rectAreaLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
		vec3 normal = geometryNormal;
		vec3 viewDir = geometryViewDir;
		vec3 position = geometryPosition;
		vec3 lightPos = rectAreaLight.position;
		vec3 halfWidth = rectAreaLight.halfWidth;
		vec3 halfHeight = rectAreaLight.halfHeight;
		vec3 lightColor = rectAreaLight.color;
		float roughness = material.roughness;
		vec3 rectCoords[ 4 ];
		rectCoords[ 0 ] = lightPos + halfWidth - halfHeight;		rectCoords[ 1 ] = lightPos - halfWidth - halfHeight;
		rectCoords[ 2 ] = lightPos - halfWidth + halfHeight;
		rectCoords[ 3 ] = lightPos + halfWidth + halfHeight;
		vec2 uv = LTC_Uv( normal, viewDir, roughness );
		vec4 t1 = texture2D( ltc_1, uv );
		vec4 t2 = texture2D( ltc_2, uv );
		mat3 mInv = mat3(
			vec3( t1.x, 0, t1.y ),
			vec3(    0, 1,    0 ),
			vec3( t1.z, 0, t1.w )
		);
		vec3 fresnel = ( material.specularColor * t2.x + ( vec3( 1.0 ) - material.specularColor ) * t2.y );
		reflectedLight.directSpecular += lightColor * fresnel * LTC_Evaluate( normal, viewDir, position, mInv, rectCoords );
		reflectedLight.directDiffuse += lightColor * material.diffuseColor * LTC_Evaluate( normal, viewDir, position, mat3( 1.0 ), rectCoords );
	}
#endif
void RE_Direct_Physical( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	float dotNL = saturate( dot( geometryNormal, directLight.direction ) );
	vec3 irradiance = dotNL * directLight.color;
	#ifdef USE_CLEARCOAT
		float dotNLcc = saturate( dot( geometryClearcoatNormal, directLight.direction ) );
		vec3 ccIrradiance = dotNLcc * directLight.color;
		clearcoatSpecularDirect += ccIrradiance * BRDF_GGX_Clearcoat( directLight.direction, geometryViewDir, geometryClearcoatNormal, material );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularDirect += irradiance * BRDF_Sheen( directLight.direction, geometryViewDir, geometryNormal, material.sheenColor, material.sheenRoughness );
	#endif
	reflectedLight.directSpecular += irradiance * BRDF_GGX( directLight.direction, geometryViewDir, geometryNormal, material );
	reflectedLight.directDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectDiffuse_Physical( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight ) {
	reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );
}
void RE_IndirectSpecular_Physical( const in vec3 radiance, const in vec3 irradiance, const in vec3 clearcoatRadiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in PhysicalMaterial material, inout ReflectedLight reflectedLight) {
	#ifdef USE_CLEARCOAT
		clearcoatSpecularIndirect += clearcoatRadiance * EnvironmentBRDF( geometryClearcoatNormal, geometryViewDir, material.clearcoatF0, material.clearcoatF90, material.clearcoatRoughness );
	#endif
	#ifdef USE_SHEEN
		sheenSpecularIndirect += irradiance * material.sheenColor * IBLSheenBRDF( geometryNormal, geometryViewDir, material.sheenRoughness );
	#endif
	vec3 singleScattering = vec3( 0.0 );
	vec3 multiScattering = vec3( 0.0 );
	vec3 cosineWeightedIrradiance = irradiance * RECIPROCAL_PI;
	#ifdef USE_IRIDESCENCE
		computeMultiscatteringIridescence( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.iridescence, material.iridescenceFresnel, material.roughness, singleScattering, multiScattering );
	#else
		computeMultiscattering( geometryNormal, geometryViewDir, material.specularColor, material.specularF90, material.roughness, singleScattering, multiScattering );
	#endif
	vec3 totalScattering = singleScattering + multiScattering;
	vec3 diffuse = material.diffuseColor * ( 1.0 - max( max( totalScattering.r, totalScattering.g ), totalScattering.b ) );
	reflectedLight.indirectSpecular += radiance * singleScattering;
	reflectedLight.indirectSpecular += multiScattering * cosineWeightedIrradiance;
	reflectedLight.indirectDiffuse += diffuse * cosineWeightedIrradiance;
}
#define RE_Direct				RE_Direct_Physical
#define RE_Direct_RectArea		RE_Direct_RectArea_Physical
#define RE_IndirectDiffuse		RE_IndirectDiffuse_Physical
#define RE_IndirectSpecular		RE_IndirectSpecular_Physical
float computeSpecularOcclusion( const in float dotNV, const in float ambientOcclusion, const in float roughness ) {
	return saturate( pow( dotNV + ambientOcclusion, exp2( - 16.0 * roughness - 1.0 ) ) - 1.0 + ambientOcclusion );
}`,Cg=`
vec3 geometryPosition = - vViewPosition;
vec3 geometryNormal = normal;
vec3 geometryViewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );
vec3 geometryClearcoatNormal = vec3( 0.0 );
#ifdef USE_CLEARCOAT
	geometryClearcoatNormal = clearcoatNormal;
#endif
#ifdef USE_IRIDESCENCE
	float dotNVi = saturate( dot( normal, geometryViewDir ) );
	if ( material.iridescenceThickness == 0.0 ) {
		material.iridescence = 0.0;
	} else {
		material.iridescence = saturate( material.iridescence );
	}
	if ( material.iridescence > 0.0 ) {
		material.iridescenceFresnel = evalIridescence( 1.0, material.iridescenceIOR, dotNVi, material.iridescenceThickness, material.specularColor );
		material.iridescenceF0 = Schlick_to_F0( material.iridescenceFresnel, 1.0, dotNVi );
	}
#endif
IncidentLight directLight;
#if ( NUM_POINT_LIGHTS > 0 ) && defined( RE_Direct )
	PointLight pointLight;
	#if defined( USE_SHADOWMAP ) && NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHTS; i ++ ) {
		pointLight = pointLights[ i ];
		getPointLightInfo( pointLight, geometryPosition, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_POINT_LIGHT_SHADOWS )
		pointLightShadow = pointLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowIntensity, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_SPOT_LIGHTS > 0 ) && defined( RE_Direct )
	SpotLight spotLight;
	vec4 spotColor;
	vec3 spotLightCoord;
	bool inSpotLightMap;
	#if defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHTS; i ++ ) {
		spotLight = spotLights[ i ];
		getSpotLightInfo( spotLight, geometryPosition, directLight );
		#if ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#define SPOT_LIGHT_MAP_INDEX UNROLLED_LOOP_INDEX
		#elif ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		#define SPOT_LIGHT_MAP_INDEX NUM_SPOT_LIGHT_MAPS
		#else
		#define SPOT_LIGHT_MAP_INDEX ( UNROLLED_LOOP_INDEX - NUM_SPOT_LIGHT_SHADOWS + NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS )
		#endif
		#if ( SPOT_LIGHT_MAP_INDEX < NUM_SPOT_LIGHT_MAPS )
			spotLightCoord = vSpotLightCoord[ i ].xyz / vSpotLightCoord[ i ].w;
			inSpotLightMap = all( lessThan( abs( spotLightCoord * 2. - 1. ), vec3( 1.0 ) ) );
			spotColor = texture2D( spotLightMap[ SPOT_LIGHT_MAP_INDEX ], spotLightCoord.xy );
			directLight.color = inSpotLightMap ? directLight.color * spotColor.rgb : directLight.color;
		#endif
		#undef SPOT_LIGHT_MAP_INDEX
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
		spotLightShadow = spotLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowIntensity, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_DIR_LIGHTS > 0 ) && defined( RE_Direct )
	DirectionalLight directionalLight;
	#if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLightShadow;
	#endif
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {
		directionalLight = directionalLights[ i ];
		getDirectionalLightInfo( directionalLight, directLight );
		#if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_DIR_LIGHT_SHADOWS )
		directionalLightShadow = directionalLightShadows[ i ];
		directLight.color *= ( directLight.visible && receiveShadow ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
		#endif
		RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )
	RectAreaLight rectAreaLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {
		rectAreaLight = rectAreaLights[ i ];
		RE_Direct_RectArea( rectAreaLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
	}
	#pragma unroll_loop_end
#endif
#if defined( RE_IndirectDiffuse )
	vec3 iblIrradiance = vec3( 0.0 );
	vec3 irradiance = getAmbientLightIrradiance( ambientLightColor );
	#if defined( USE_LIGHT_PROBES )
		irradiance += getLightProbeIrradiance( lightProbe, geometryNormal );
	#endif
	#if ( NUM_HEMI_LIGHTS > 0 )
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {
			irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal );
		}
		#pragma unroll_loop_end
	#endif
#endif
#if defined( RE_IndirectSpecular )
	vec3 radiance = vec3( 0.0 );
	vec3 clearcoatRadiance = vec3( 0.0 );
#endif`,Pg=`#if defined( RE_IndirectDiffuse )
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		vec3 lightMapIrradiance = lightMapTexel.rgb * lightMapIntensity;
		irradiance += lightMapIrradiance;
	#endif
	#if defined( USE_ENVMAP ) && defined( STANDARD ) && defined( ENVMAP_TYPE_CUBE_UV )
		iblIrradiance += getIBLIrradiance( geometryNormal );
	#endif
#endif
#if defined( USE_ENVMAP ) && defined( RE_IndirectSpecular )
	#ifdef USE_ANISOTROPY
		radiance += getIBLAnisotropyRadiance( geometryViewDir, geometryNormal, material.roughness, material.anisotropyB, material.anisotropy );
	#else
		radiance += getIBLRadiance( geometryViewDir, geometryNormal, material.roughness );
	#endif
	#ifdef USE_CLEARCOAT
		clearcoatRadiance += getIBLRadiance( geometryViewDir, geometryClearcoatNormal, material.clearcoatRoughness );
	#endif
#endif`,Ig=`#if defined( RE_IndirectDiffuse )
	RE_IndirectDiffuse( irradiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif
#if defined( RE_IndirectSpecular )
	RE_IndirectSpecular( radiance, iblIrradiance, clearcoatRadiance, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, reflectedLight );
#endif`,Lg=`#if defined( USE_LOGDEPTHBUF )
	gl_FragDepth = vIsPerspective == 0.0 ? gl_FragCoord.z : log2( vFragDepth ) * logDepthBufFC * 0.5;
#endif`,Dg=`#if defined( USE_LOGDEPTHBUF )
	uniform float logDepthBufFC;
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Ng=`#ifdef USE_LOGDEPTHBUF
	varying float vFragDepth;
	varying float vIsPerspective;
#endif`,Ug=`#ifdef USE_LOGDEPTHBUF
	vFragDepth = 1.0 + gl_Position.w;
	vIsPerspective = float( isPerspectiveMatrix( projectionMatrix ) );
#endif`,Fg=`#ifdef USE_MAP
	vec4 sampledDiffuseColor = texture2D( map, vMapUv );
	#ifdef DECODE_VIDEO_TEXTURE
		sampledDiffuseColor = sRGBTransferEOTF( sampledDiffuseColor );
	#endif
	diffuseColor *= sampledDiffuseColor;
#endif`,Og=`#ifdef USE_MAP
	uniform sampler2D map;
#endif`,Bg=`#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
	#if defined( USE_POINTS_UV )
		vec2 uv = vUv;
	#else
		vec2 uv = ( uvTransform * vec3( gl_PointCoord.x, 1.0 - gl_PointCoord.y, 1 ) ).xy;
	#endif
#endif
#ifdef USE_MAP
	diffuseColor *= texture2D( map, uv );
#endif
#ifdef USE_ALPHAMAP
	diffuseColor.a *= texture2D( alphaMap, uv ).g;
#endif`,zg=`#if defined( USE_POINTS_UV )
	varying vec2 vUv;
#else
	#if defined( USE_MAP ) || defined( USE_ALPHAMAP )
		uniform mat3 uvTransform;
	#endif
#endif
#ifdef USE_MAP
	uniform sampler2D map;
#endif
#ifdef USE_ALPHAMAP
	uniform sampler2D alphaMap;
#endif`,kg=`float metalnessFactor = metalness;
#ifdef USE_METALNESSMAP
	vec4 texelMetalness = texture2D( metalnessMap, vMetalnessMapUv );
	metalnessFactor *= texelMetalness.b;
#endif`,Hg=`#ifdef USE_METALNESSMAP
	uniform sampler2D metalnessMap;
#endif`,Gg=`#ifdef USE_INSTANCING_MORPH
	float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	float morphTargetBaseInfluence = texelFetch( morphTexture, ivec2( 0, gl_InstanceID ), 0 ).r;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		morphTargetInfluences[i] =  texelFetch( morphTexture, ivec2( i + 1, gl_InstanceID ), 0 ).r;
	}
#endif`,Vg=`#if defined( USE_MORPHCOLORS )
	vColor *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		#if defined( USE_COLOR_ALPHA )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ) * morphTargetInfluences[ i ];
		#elif defined( USE_COLOR )
			if ( morphTargetInfluences[ i ] != 0.0 ) vColor += getMorph( gl_VertexID, i, 2 ).rgb * morphTargetInfluences[ i ];
		#endif
	}
#endif`,Wg=`#ifdef USE_MORPHNORMALS
	objectNormal *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) objectNormal += getMorph( gl_VertexID, i, 1 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,Xg=`#ifdef USE_MORPHTARGETS
	#ifndef USE_INSTANCING_MORPH
		uniform float morphTargetBaseInfluence;
		uniform float morphTargetInfluences[ MORPHTARGETS_COUNT ];
	#endif
	uniform sampler2DArray morphTargetsTexture;
	uniform ivec2 morphTargetsTextureSize;
	vec4 getMorph( const in int vertexIndex, const in int morphTargetIndex, const in int offset ) {
		int texelIndex = vertexIndex * MORPHTARGETS_TEXTURE_STRIDE + offset;
		int y = texelIndex / morphTargetsTextureSize.x;
		int x = texelIndex - y * morphTargetsTextureSize.x;
		ivec3 morphUV = ivec3( x, y, morphTargetIndex );
		return texelFetch( morphTargetsTexture, morphUV, 0 );
	}
#endif`,jg=`#ifdef USE_MORPHTARGETS
	transformed *= morphTargetBaseInfluence;
	for ( int i = 0; i < MORPHTARGETS_COUNT; i ++ ) {
		if ( morphTargetInfluences[ i ] != 0.0 ) transformed += getMorph( gl_VertexID, i, 0 ).xyz * morphTargetInfluences[ i ];
	}
#endif`,qg=`float faceDirection = gl_FrontFacing ? 1.0 : - 1.0;
#ifdef FLAT_SHADED
	vec3 fdx = dFdx( vViewPosition );
	vec3 fdy = dFdy( vViewPosition );
	vec3 normal = normalize( cross( fdx, fdy ) );
#else
	vec3 normal = normalize( vNormal );
	#ifdef DOUBLE_SIDED
		normal *= faceDirection;
	#endif
#endif
#if defined( USE_NORMALMAP_TANGENTSPACE ) || defined( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY )
	#ifdef USE_TANGENT
		mat3 tbn = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn = getTangentFrame( - vViewPosition, normal,
		#if defined( USE_NORMALMAP )
			vNormalMapUv
		#elif defined( USE_CLEARCOAT_NORMALMAP )
			vClearcoatNormalMapUv
		#else
			vUv
		#endif
		);
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn[0] *= faceDirection;
		tbn[1] *= faceDirection;
	#endif
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	#ifdef USE_TANGENT
		mat3 tbn2 = mat3( normalize( vTangent ), normalize( vBitangent ), normal );
	#else
		mat3 tbn2 = getTangentFrame( - vViewPosition, normal, vClearcoatNormalMapUv );
	#endif
	#if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )
		tbn2[0] *= faceDirection;
		tbn2[1] *= faceDirection;
	#endif
#endif
vec3 nonPerturbedNormal = normal;`,Yg=`#ifdef USE_NORMALMAP_OBJECTSPACE
	normal = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	#ifdef FLIP_SIDED
		normal = - normal;
	#endif
	#ifdef DOUBLE_SIDED
		normal = normal * faceDirection;
	#endif
	normal = normalize( normalMatrix * normal );
#elif defined( USE_NORMALMAP_TANGENTSPACE )
	vec3 mapN = texture2D( normalMap, vNormalMapUv ).xyz * 2.0 - 1.0;
	mapN.xy *= normalScale;
	normal = normalize( tbn * mapN );
#elif defined( USE_BUMPMAP )
	normal = perturbNormalArb( - vViewPosition, normal, dHdxy_fwd(), faceDirection );
#endif`,Kg=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,$g=`#ifndef FLAT_SHADED
	varying vec3 vNormal;
	#ifdef USE_TANGENT
		varying vec3 vTangent;
		varying vec3 vBitangent;
	#endif
#endif`,Zg=`#ifndef FLAT_SHADED
	vNormal = normalize( transformedNormal );
	#ifdef USE_TANGENT
		vTangent = normalize( transformedTangent );
		vBitangent = normalize( cross( vNormal, vTangent ) * tangent.w );
	#endif
#endif`,Jg=`#ifdef USE_NORMALMAP
	uniform sampler2D normalMap;
	uniform vec2 normalScale;
#endif
#ifdef USE_NORMALMAP_OBJECTSPACE
	uniform mat3 normalMatrix;
#endif
#if ! defined ( USE_TANGENT ) && ( defined ( USE_NORMALMAP_TANGENTSPACE ) || defined ( USE_CLEARCOAT_NORMALMAP ) || defined( USE_ANISOTROPY ) )
	mat3 getTangentFrame( vec3 eye_pos, vec3 surf_norm, vec2 uv ) {
		vec3 q0 = dFdx( eye_pos.xyz );
		vec3 q1 = dFdy( eye_pos.xyz );
		vec2 st0 = dFdx( uv.st );
		vec2 st1 = dFdy( uv.st );
		vec3 N = surf_norm;
		vec3 q1perp = cross( q1, N );
		vec3 q0perp = cross( N, q0 );
		vec3 T = q1perp * st0.x + q0perp * st1.x;
		vec3 B = q1perp * st0.y + q0perp * st1.y;
		float det = max( dot( T, T ), dot( B, B ) );
		float scale = ( det == 0.0 ) ? 0.0 : inversesqrt( det );
		return mat3( T * scale, B * scale, N );
	}
#endif`,Qg=`#ifdef USE_CLEARCOAT
	vec3 clearcoatNormal = nonPerturbedNormal;
#endif`,e_=`#ifdef USE_CLEARCOAT_NORMALMAP
	vec3 clearcoatMapN = texture2D( clearcoatNormalMap, vClearcoatNormalMapUv ).xyz * 2.0 - 1.0;
	clearcoatMapN.xy *= clearcoatNormalScale;
	clearcoatNormal = normalize( tbn2 * clearcoatMapN );
#endif`,t_=`#ifdef USE_CLEARCOATMAP
	uniform sampler2D clearcoatMap;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform sampler2D clearcoatNormalMap;
	uniform vec2 clearcoatNormalScale;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform sampler2D clearcoatRoughnessMap;
#endif`,n_=`#ifdef USE_IRIDESCENCEMAP
	uniform sampler2D iridescenceMap;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform sampler2D iridescenceThicknessMap;
#endif`,i_=`#ifdef OPAQUE
diffuseColor.a = 1.0;
#endif
#ifdef USE_TRANSMISSION
diffuseColor.a *= material.transmissionAlpha;
#endif
gl_FragColor = vec4( outgoingLight, diffuseColor.a );`,r_=`vec3 packNormalToRGB( const in vec3 normal ) {
	return normalize( normal ) * 0.5 + 0.5;
}
vec3 unpackRGBToNormal( const in vec3 rgb ) {
	return 2.0 * rgb.xyz - 1.0;
}
const float PackUpscale = 256. / 255.;const float UnpackDownscale = 255. / 256.;const float ShiftRight8 = 1. / 256.;
const float Inv255 = 1. / 255.;
const vec4 PackFactors = vec4( 1.0, 256.0, 256.0 * 256.0, 256.0 * 256.0 * 256.0 );
const vec2 UnpackFactors2 = vec2( UnpackDownscale, 1.0 / PackFactors.g );
const vec3 UnpackFactors3 = vec3( UnpackDownscale / PackFactors.rg, 1.0 / PackFactors.b );
const vec4 UnpackFactors4 = vec4( UnpackDownscale / PackFactors.rgb, 1.0 / PackFactors.a );
vec4 packDepthToRGBA( const in float v ) {
	if( v <= 0.0 )
		return vec4( 0., 0., 0., 0. );
	if( v >= 1.0 )
		return vec4( 1., 1., 1., 1. );
	float vuf;
	float af = modf( v * PackFactors.a, vuf );
	float bf = modf( vuf * ShiftRight8, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec4( vuf * Inv255, gf * PackUpscale, bf * PackUpscale, af );
}
vec3 packDepthToRGB( const in float v ) {
	if( v <= 0.0 )
		return vec3( 0., 0., 0. );
	if( v >= 1.0 )
		return vec3( 1., 1., 1. );
	float vuf;
	float bf = modf( v * PackFactors.b, vuf );
	float gf = modf( vuf * ShiftRight8, vuf );
	return vec3( vuf * Inv255, gf * PackUpscale, bf );
}
vec2 packDepthToRG( const in float v ) {
	if( v <= 0.0 )
		return vec2( 0., 0. );
	if( v >= 1.0 )
		return vec2( 1., 1. );
	float vuf;
	float gf = modf( v * 256., vuf );
	return vec2( vuf * Inv255, gf );
}
float unpackRGBAToDepth( const in vec4 v ) {
	return dot( v, UnpackFactors4 );
}
float unpackRGBToDepth( const in vec3 v ) {
	return dot( v, UnpackFactors3 );
}
float unpackRGToDepth( const in vec2 v ) {
	return v.r * UnpackFactors2.r + v.g * UnpackFactors2.g;
}
vec4 pack2HalfToRGBA( const in vec2 v ) {
	vec4 r = vec4( v.x, fract( v.x * 255.0 ), v.y, fract( v.y * 255.0 ) );
	return vec4( r.x - r.y / 255.0, r.y, r.z - r.w / 255.0, r.w );
}
vec2 unpackRGBATo2Half( const in vec4 v ) {
	return vec2( v.x + ( v.y / 255.0 ), v.z + ( v.w / 255.0 ) );
}
float viewZToOrthographicDepth( const in float viewZ, const in float near, const in float far ) {
	return ( viewZ + near ) / ( near - far );
}
float orthographicDepthToViewZ( const in float depth, const in float near, const in float far ) {
	return depth * ( near - far ) - near;
}
float viewZToPerspectiveDepth( const in float viewZ, const in float near, const in float far ) {
	return ( ( near + viewZ ) * far ) / ( ( far - near ) * viewZ );
}
float perspectiveDepthToViewZ( const in float depth, const in float near, const in float far ) {
	return ( near * far ) / ( ( far - near ) * depth - far );
}`,s_=`#ifdef PREMULTIPLIED_ALPHA
	gl_FragColor.rgb *= gl_FragColor.a;
#endif`,a_=`vec4 mvPosition = vec4( transformed, 1.0 );
#ifdef USE_BATCHING
	mvPosition = batchingMatrix * mvPosition;
#endif
#ifdef USE_INSTANCING
	mvPosition = instanceMatrix * mvPosition;
#endif
mvPosition = modelViewMatrix * mvPosition;
gl_Position = projectionMatrix * mvPosition;`,o_=`#ifdef DITHERING
	gl_FragColor.rgb = dithering( gl_FragColor.rgb );
#endif`,l_=`#ifdef DITHERING
	vec3 dithering( vec3 color ) {
		float grid_position = rand( gl_FragCoord.xy );
		vec3 dither_shift_RGB = vec3( 0.25 / 255.0, -0.25 / 255.0, 0.25 / 255.0 );
		dither_shift_RGB = mix( 2.0 * dither_shift_RGB, -2.0 * dither_shift_RGB, grid_position );
		return color + dither_shift_RGB;
	}
#endif`,c_=`float roughnessFactor = roughness;
#ifdef USE_ROUGHNESSMAP
	vec4 texelRoughness = texture2D( roughnessMap, vRoughnessMapUv );
	roughnessFactor *= texelRoughness.g;
#endif`,d_=`#ifdef USE_ROUGHNESSMAP
	uniform sampler2D roughnessMap;
#endif`,u_=`#if NUM_SPOT_LIGHT_COORDS > 0
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#if NUM_SPOT_LIGHT_MAPS > 0
	uniform sampler2D spotLightMap[ NUM_SPOT_LIGHT_MAPS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform sampler2D directionalShadowMap[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		uniform sampler2D spotShadowMap[ NUM_SPOT_LIGHT_SHADOWS ];
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform sampler2D pointShadowMap[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
	float texture2DCompare( sampler2D depths, vec2 uv, float compare ) {
		float depth = unpackRGBAToDepth( texture2D( depths, uv ) );
		#ifdef USE_REVERSEDEPTHBUF
			return step( depth, compare );
		#else
			return step( compare, depth );
		#endif
	}
	vec2 texture2DDistribution( sampler2D shadow, vec2 uv ) {
		return unpackRGBATo2Half( texture2D( shadow, uv ) );
	}
	float VSMShadow (sampler2D shadow, vec2 uv, float compare ){
		float occlusion = 1.0;
		vec2 distribution = texture2DDistribution( shadow, uv );
		#ifdef USE_REVERSEDEPTHBUF
			float hard_shadow = step( distribution.x, compare );
		#else
			float hard_shadow = step( compare , distribution.x );
		#endif
		if (hard_shadow != 1.0 ) {
			float distance = compare - distribution.x ;
			float variance = max( 0.00000, distribution.y * distribution.y );
			float softness_probability = variance / (variance + distance * distance );			softness_probability = clamp( ( softness_probability - 0.3 ) / ( 0.95 - 0.3 ), 0.0, 1.0 );			occlusion = clamp( max( hard_shadow, softness_probability ), 0.0, 1.0 );
		}
		return occlusion;
	}
	float getShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord ) {
		float shadow = 1.0;
		shadowCoord.xyz /= shadowCoord.w;
		shadowCoord.z += shadowBias;
		bool inFrustum = shadowCoord.x >= 0.0 && shadowCoord.x <= 1.0 && shadowCoord.y >= 0.0 && shadowCoord.y <= 1.0;
		bool frustumTest = inFrustum && shadowCoord.z <= 1.0;
		if ( frustumTest ) {
		#if defined( SHADOWMAP_TYPE_PCF )
			vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
			float dx0 = - texelSize.x * shadowRadius;
			float dy0 = - texelSize.y * shadowRadius;
			float dx1 = + texelSize.x * shadowRadius;
			float dy1 = + texelSize.y * shadowRadius;
			float dx2 = dx0 / 2.0;
			float dy2 = dy0 / 2.0;
			float dx3 = dx1 / 2.0;
			float dy3 = dy1 / 2.0;
			shadow = (
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, dy0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, dy2 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy, shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx2, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx3, dy3 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx0, dy1 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( 0.0, dy1 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, shadowCoord.xy + vec2( dx1, dy1 ), shadowCoord.z )
			) * ( 1.0 / 17.0 );
		#elif defined( SHADOWMAP_TYPE_PCF_SOFT )
			vec2 texelSize = vec2( 1.0 ) / shadowMapSize;
			float dx = texelSize.x;
			float dy = texelSize.y;
			vec2 uv = shadowCoord.xy;
			vec2 f = fract( uv * shadowMapSize + 0.5 );
			uv -= f * texelSize;
			shadow = (
				texture2DCompare( shadowMap, uv, shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + vec2( dx, 0.0 ), shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + vec2( 0.0, dy ), shadowCoord.z ) +
				texture2DCompare( shadowMap, uv + texelSize, shadowCoord.z ) +
				mix( texture2DCompare( shadowMap, uv + vec2( -dx, 0.0 ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, 0.0 ), shadowCoord.z ),
					 f.x ) +
				mix( texture2DCompare( shadowMap, uv + vec2( -dx, dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, dy ), shadowCoord.z ),
					 f.x ) +
				mix( texture2DCompare( shadowMap, uv + vec2( 0.0, -dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( 0.0, 2.0 * dy ), shadowCoord.z ),
					 f.y ) +
				mix( texture2DCompare( shadowMap, uv + vec2( dx, -dy ), shadowCoord.z ),
					 texture2DCompare( shadowMap, uv + vec2( dx, 2.0 * dy ), shadowCoord.z ),
					 f.y ) +
				mix( mix( texture2DCompare( shadowMap, uv + vec2( -dx, -dy ), shadowCoord.z ),
						  texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, -dy ), shadowCoord.z ),
						  f.x ),
					 mix( texture2DCompare( shadowMap, uv + vec2( -dx, 2.0 * dy ), shadowCoord.z ),
						  texture2DCompare( shadowMap, uv + vec2( 2.0 * dx, 2.0 * dy ), shadowCoord.z ),
						  f.x ),
					 f.y )
			) * ( 1.0 / 9.0 );
		#elif defined( SHADOWMAP_TYPE_VSM )
			shadow = VSMShadow( shadowMap, shadowCoord.xy, shadowCoord.z );
		#else
			shadow = texture2DCompare( shadowMap, shadowCoord.xy, shadowCoord.z );
		#endif
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
	vec2 cubeToUV( vec3 v, float texelSizeY ) {
		vec3 absV = abs( v );
		float scaleToCube = 1.0 / max( absV.x, max( absV.y, absV.z ) );
		absV *= scaleToCube;
		v *= scaleToCube * ( 1.0 - 2.0 * texelSizeY );
		vec2 planar = v.xy;
		float almostATexel = 1.5 * texelSizeY;
		float almostOne = 1.0 - almostATexel;
		if ( absV.z >= almostOne ) {
			if ( v.z > 0.0 )
				planar.x = 4.0 - v.x;
		} else if ( absV.x >= almostOne ) {
			float signX = sign( v.x );
			planar.x = v.z * signX + 2.0 * signX;
		} else if ( absV.y >= almostOne ) {
			float signY = sign( v.y );
			planar.x = v.x + 2.0 * signY + 2.0;
			planar.y = v.z * signY - 2.0;
		}
		return vec2( 0.125, 0.25 ) * planar + vec2( 0.375, 0.75 );
	}
	float getPointShadow( sampler2D shadowMap, vec2 shadowMapSize, float shadowIntensity, float shadowBias, float shadowRadius, vec4 shadowCoord, float shadowCameraNear, float shadowCameraFar ) {
		float shadow = 1.0;
		vec3 lightToPosition = shadowCoord.xyz;
		
		float lightToPositionLength = length( lightToPosition );
		if ( lightToPositionLength - shadowCameraFar <= 0.0 && lightToPositionLength - shadowCameraNear >= 0.0 ) {
			float dp = ( lightToPositionLength - shadowCameraNear ) / ( shadowCameraFar - shadowCameraNear );			dp += shadowBias;
			vec3 bd3D = normalize( lightToPosition );
			vec2 texelSize = vec2( 1.0 ) / ( shadowMapSize * vec2( 4.0, 2.0 ) );
			#if defined( SHADOWMAP_TYPE_PCF ) || defined( SHADOWMAP_TYPE_PCF_SOFT ) || defined( SHADOWMAP_TYPE_VSM )
				vec2 offset = vec2( - 1, 1 ) * shadowRadius * texelSize.y;
				shadow = (
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xyy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yyy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xyx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yyx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xxy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yxy, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.xxx, texelSize.y ), dp ) +
					texture2DCompare( shadowMap, cubeToUV( bd3D + offset.yxx, texelSize.y ), dp )
				) * ( 1.0 / 9.0 );
			#else
				shadow = texture2DCompare( shadowMap, cubeToUV( bd3D, texelSize.y ), dp );
			#endif
		}
		return mix( 1.0, shadow, shadowIntensity );
	}
#endif`,h_=`#if NUM_SPOT_LIGHT_COORDS > 0
	uniform mat4 spotLightMatrix[ NUM_SPOT_LIGHT_COORDS ];
	varying vec4 vSpotLightCoord[ NUM_SPOT_LIGHT_COORDS ];
#endif
#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
		uniform mat4 directionalShadowMatrix[ NUM_DIR_LIGHT_SHADOWS ];
		varying vec4 vDirectionalShadowCoord[ NUM_DIR_LIGHT_SHADOWS ];
		struct DirectionalLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform DirectionalLightShadow directionalLightShadows[ NUM_DIR_LIGHT_SHADOWS ];
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
		struct SpotLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
		};
		uniform SpotLightShadow spotLightShadows[ NUM_SPOT_LIGHT_SHADOWS ];
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		uniform mat4 pointShadowMatrix[ NUM_POINT_LIGHT_SHADOWS ];
		varying vec4 vPointShadowCoord[ NUM_POINT_LIGHT_SHADOWS ];
		struct PointLightShadow {
			float shadowIntensity;
			float shadowBias;
			float shadowNormalBias;
			float shadowRadius;
			vec2 shadowMapSize;
			float shadowCameraNear;
			float shadowCameraFar;
		};
		uniform PointLightShadow pointLightShadows[ NUM_POINT_LIGHT_SHADOWS ];
	#endif
#endif`,f_=`#if ( defined( USE_SHADOWMAP ) && ( NUM_DIR_LIGHT_SHADOWS > 0 || NUM_POINT_LIGHT_SHADOWS > 0 ) ) || ( NUM_SPOT_LIGHT_COORDS > 0 )
	vec3 shadowWorldNormal = inverseTransformDirection( transformedNormal, viewMatrix );
	vec4 shadowWorldPosition;
#endif
#if defined( USE_SHADOWMAP )
	#if NUM_DIR_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * directionalLightShadows[ i ].shadowNormalBias, 0 );
			vDirectionalShadowCoord[ i ] = directionalShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
		#pragma unroll_loop_start
		for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
			shadowWorldPosition = worldPosition + vec4( shadowWorldNormal * pointLightShadows[ i ].shadowNormalBias, 0 );
			vPointShadowCoord[ i ] = pointShadowMatrix[ i ] * shadowWorldPosition;
		}
		#pragma unroll_loop_end
	#endif
#endif
#if NUM_SPOT_LIGHT_COORDS > 0
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_COORDS; i ++ ) {
		shadowWorldPosition = worldPosition;
		#if ( defined( USE_SHADOWMAP ) && UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
			shadowWorldPosition.xyz += shadowWorldNormal * spotLightShadows[ i ].shadowNormalBias;
		#endif
		vSpotLightCoord[ i ] = spotLightMatrix[ i ] * shadowWorldPosition;
	}
	#pragma unroll_loop_end
#endif`,p_=`float getShadowMask() {
	float shadow = 1.0;
	#ifdef USE_SHADOWMAP
	#if NUM_DIR_LIGHT_SHADOWS > 0
	DirectionalLightShadow directionalLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_DIR_LIGHT_SHADOWS; i ++ ) {
		directionalLight = directionalLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( directionalShadowMap[ i ], directionalLight.shadowMapSize, directionalLight.shadowIntensity, directionalLight.shadowBias, directionalLight.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_SPOT_LIGHT_SHADOWS > 0
	SpotLightShadow spotLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_SPOT_LIGHT_SHADOWS; i ++ ) {
		spotLight = spotLightShadows[ i ];
		shadow *= receiveShadow ? getShadow( spotShadowMap[ i ], spotLight.shadowMapSize, spotLight.shadowIntensity, spotLight.shadowBias, spotLight.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#if NUM_POINT_LIGHT_SHADOWS > 0
	PointLightShadow pointLight;
	#pragma unroll_loop_start
	for ( int i = 0; i < NUM_POINT_LIGHT_SHADOWS; i ++ ) {
		pointLight = pointLightShadows[ i ];
		shadow *= receiveShadow ? getPointShadow( pointShadowMap[ i ], pointLight.shadowMapSize, pointLight.shadowIntensity, pointLight.shadowBias, pointLight.shadowRadius, vPointShadowCoord[ i ], pointLight.shadowCameraNear, pointLight.shadowCameraFar ) : 1.0;
	}
	#pragma unroll_loop_end
	#endif
	#endif
	return shadow;
}`,m_=`#ifdef USE_SKINNING
	mat4 boneMatX = getBoneMatrix( skinIndex.x );
	mat4 boneMatY = getBoneMatrix( skinIndex.y );
	mat4 boneMatZ = getBoneMatrix( skinIndex.z );
	mat4 boneMatW = getBoneMatrix( skinIndex.w );
#endif`,g_=`#ifdef USE_SKINNING
	uniform mat4 bindMatrix;
	uniform mat4 bindMatrixInverse;
	uniform highp sampler2D boneTexture;
	mat4 getBoneMatrix( const in float i ) {
		int size = textureSize( boneTexture, 0 ).x;
		int j = int( i ) * 4;
		int x = j % size;
		int y = j / size;
		vec4 v1 = texelFetch( boneTexture, ivec2( x, y ), 0 );
		vec4 v2 = texelFetch( boneTexture, ivec2( x + 1, y ), 0 );
		vec4 v3 = texelFetch( boneTexture, ivec2( x + 2, y ), 0 );
		vec4 v4 = texelFetch( boneTexture, ivec2( x + 3, y ), 0 );
		return mat4( v1, v2, v3, v4 );
	}
#endif`,__=`#ifdef USE_SKINNING
	vec4 skinVertex = bindMatrix * vec4( transformed, 1.0 );
	vec4 skinned = vec4( 0.0 );
	skinned += boneMatX * skinVertex * skinWeight.x;
	skinned += boneMatY * skinVertex * skinWeight.y;
	skinned += boneMatZ * skinVertex * skinWeight.z;
	skinned += boneMatW * skinVertex * skinWeight.w;
	transformed = ( bindMatrixInverse * skinned ).xyz;
#endif`,y_=`#ifdef USE_SKINNING
	mat4 skinMatrix = mat4( 0.0 );
	skinMatrix += skinWeight.x * boneMatX;
	skinMatrix += skinWeight.y * boneMatY;
	skinMatrix += skinWeight.z * boneMatZ;
	skinMatrix += skinWeight.w * boneMatW;
	skinMatrix = bindMatrixInverse * skinMatrix * bindMatrix;
	objectNormal = vec4( skinMatrix * vec4( objectNormal, 0.0 ) ).xyz;
	#ifdef USE_TANGENT
		objectTangent = vec4( skinMatrix * vec4( objectTangent, 0.0 ) ).xyz;
	#endif
#endif`,x_=`float specularStrength;
#ifdef USE_SPECULARMAP
	vec4 texelSpecular = texture2D( specularMap, vSpecularMapUv );
	specularStrength = texelSpecular.r;
#else
	specularStrength = 1.0;
#endif`,v_=`#ifdef USE_SPECULARMAP
	uniform sampler2D specularMap;
#endif`,M_=`#if defined( TONE_MAPPING )
	gl_FragColor.rgb = toneMapping( gl_FragColor.rgb );
#endif`,b_=`#ifndef saturate
#define saturate( a ) clamp( a, 0.0, 1.0 )
#endif
uniform float toneMappingExposure;
vec3 LinearToneMapping( vec3 color ) {
	return saturate( toneMappingExposure * color );
}
vec3 ReinhardToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	return saturate( color / ( vec3( 1.0 ) + color ) );
}
vec3 CineonToneMapping( vec3 color ) {
	color *= toneMappingExposure;
	color = max( vec3( 0.0 ), color - 0.004 );
	return pow( ( color * ( 6.2 * color + 0.5 ) ) / ( color * ( 6.2 * color + 1.7 ) + 0.06 ), vec3( 2.2 ) );
}
vec3 RRTAndODTFit( vec3 v ) {
	vec3 a = v * ( v + 0.0245786 ) - 0.000090537;
	vec3 b = v * ( 0.983729 * v + 0.4329510 ) + 0.238081;
	return a / b;
}
vec3 ACESFilmicToneMapping( vec3 color ) {
	const mat3 ACESInputMat = mat3(
		vec3( 0.59719, 0.07600, 0.02840 ),		vec3( 0.35458, 0.90834, 0.13383 ),
		vec3( 0.04823, 0.01566, 0.83777 )
	);
	const mat3 ACESOutputMat = mat3(
		vec3(  1.60475, -0.10208, -0.00327 ),		vec3( -0.53108,  1.10813, -0.07276 ),
		vec3( -0.07367, -0.00605,  1.07602 )
	);
	color *= toneMappingExposure / 0.6;
	color = ACESInputMat * color;
	color = RRTAndODTFit( color );
	color = ACESOutputMat * color;
	return saturate( color );
}
const mat3 LINEAR_REC2020_TO_LINEAR_SRGB = mat3(
	vec3( 1.6605, - 0.1246, - 0.0182 ),
	vec3( - 0.5876, 1.1329, - 0.1006 ),
	vec3( - 0.0728, - 0.0083, 1.1187 )
);
const mat3 LINEAR_SRGB_TO_LINEAR_REC2020 = mat3(
	vec3( 0.6274, 0.0691, 0.0164 ),
	vec3( 0.3293, 0.9195, 0.0880 ),
	vec3( 0.0433, 0.0113, 0.8956 )
);
vec3 agxDefaultContrastApprox( vec3 x ) {
	vec3 x2 = x * x;
	vec3 x4 = x2 * x2;
	return + 15.5 * x4 * x2
		- 40.14 * x4 * x
		+ 31.96 * x4
		- 6.868 * x2 * x
		+ 0.4298 * x2
		+ 0.1191 * x
		- 0.00232;
}
vec3 AgXToneMapping( vec3 color ) {
	const mat3 AgXInsetMatrix = mat3(
		vec3( 0.856627153315983, 0.137318972929847, 0.11189821299995 ),
		vec3( 0.0951212405381588, 0.761241990602591, 0.0767994186031903 ),
		vec3( 0.0482516061458583, 0.101439036467562, 0.811302368396859 )
	);
	const mat3 AgXOutsetMatrix = mat3(
		vec3( 1.1271005818144368, - 0.1413297634984383, - 0.14132976349843826 ),
		vec3( - 0.11060664309660323, 1.157823702216272, - 0.11060664309660294 ),
		vec3( - 0.016493938717834573, - 0.016493938717834257, 1.2519364065950405 )
	);
	const float AgxMinEv = - 12.47393;	const float AgxMaxEv = 4.026069;
	color *= toneMappingExposure;
	color = LINEAR_SRGB_TO_LINEAR_REC2020 * color;
	color = AgXInsetMatrix * color;
	color = max( color, 1e-10 );	color = log2( color );
	color = ( color - AgxMinEv ) / ( AgxMaxEv - AgxMinEv );
	color = clamp( color, 0.0, 1.0 );
	color = agxDefaultContrastApprox( color );
	color = AgXOutsetMatrix * color;
	color = pow( max( vec3( 0.0 ), color ), vec3( 2.2 ) );
	color = LINEAR_REC2020_TO_LINEAR_SRGB * color;
	color = clamp( color, 0.0, 1.0 );
	return color;
}
vec3 NeutralToneMapping( vec3 color ) {
	const float StartCompression = 0.8 - 0.04;
	const float Desaturation = 0.15;
	color *= toneMappingExposure;
	float x = min( color.r, min( color.g, color.b ) );
	float offset = x < 0.08 ? x - 6.25 * x * x : 0.04;
	color -= offset;
	float peak = max( color.r, max( color.g, color.b ) );
	if ( peak < StartCompression ) return color;
	float d = 1. - StartCompression;
	float newPeak = 1. - d * d / ( peak + d - StartCompression );
	color *= newPeak / peak;
	float g = 1. - 1. / ( Desaturation * ( peak - newPeak ) + 1. );
	return mix( color, vec3( newPeak ), g );
}
vec3 CustomToneMapping( vec3 color ) { return color; }`,S_=`#ifdef USE_TRANSMISSION
	material.transmission = transmission;
	material.transmissionAlpha = 1.0;
	material.thickness = thickness;
	material.attenuationDistance = attenuationDistance;
	material.attenuationColor = attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		material.transmission *= texture2D( transmissionMap, vTransmissionMapUv ).r;
	#endif
	#ifdef USE_THICKNESSMAP
		material.thickness *= texture2D( thicknessMap, vThicknessMapUv ).g;
	#endif
	vec3 pos = vWorldPosition;
	vec3 v = normalize( cameraPosition - pos );
	vec3 n = inverseTransformDirection( normal, viewMatrix );
	vec4 transmitted = getIBLVolumeRefraction(
		n, v, material.roughness, material.diffuseColor, material.specularColor, material.specularF90,
		pos, modelMatrix, viewMatrix, projectionMatrix, material.dispersion, material.ior, material.thickness,
		material.attenuationColor, material.attenuationDistance );
	material.transmissionAlpha = mix( material.transmissionAlpha, transmitted.a, material.transmission );
	totalDiffuse = mix( totalDiffuse, transmitted.rgb, material.transmission );
#endif`,w_=`#ifdef USE_TRANSMISSION
	uniform float transmission;
	uniform float thickness;
	uniform float attenuationDistance;
	uniform vec3 attenuationColor;
	#ifdef USE_TRANSMISSIONMAP
		uniform sampler2D transmissionMap;
	#endif
	#ifdef USE_THICKNESSMAP
		uniform sampler2D thicknessMap;
	#endif
	uniform vec2 transmissionSamplerSize;
	uniform sampler2D transmissionSamplerMap;
	uniform mat4 modelMatrix;
	uniform mat4 projectionMatrix;
	varying vec3 vWorldPosition;
	float w0( float a ) {
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - a + 3.0 ) - 3.0 ) + 1.0 );
	}
	float w1( float a ) {
		return ( 1.0 / 6.0 ) * ( a *  a * ( 3.0 * a - 6.0 ) + 4.0 );
	}
	float w2( float a ){
		return ( 1.0 / 6.0 ) * ( a * ( a * ( - 3.0 * a + 3.0 ) + 3.0 ) + 1.0 );
	}
	float w3( float a ) {
		return ( 1.0 / 6.0 ) * ( a * a * a );
	}
	float g0( float a ) {
		return w0( a ) + w1( a );
	}
	float g1( float a ) {
		return w2( a ) + w3( a );
	}
	float h0( float a ) {
		return - 1.0 + w1( a ) / ( w0( a ) + w1( a ) );
	}
	float h1( float a ) {
		return 1.0 + w3( a ) / ( w2( a ) + w3( a ) );
	}
	vec4 bicubic( sampler2D tex, vec2 uv, vec4 texelSize, float lod ) {
		uv = uv * texelSize.zw + 0.5;
		vec2 iuv = floor( uv );
		vec2 fuv = fract( uv );
		float g0x = g0( fuv.x );
		float g1x = g1( fuv.x );
		float h0x = h0( fuv.x );
		float h1x = h1( fuv.x );
		float h0y = h0( fuv.y );
		float h1y = h1( fuv.y );
		vec2 p0 = ( vec2( iuv.x + h0x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p1 = ( vec2( iuv.x + h1x, iuv.y + h0y ) - 0.5 ) * texelSize.xy;
		vec2 p2 = ( vec2( iuv.x + h0x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		vec2 p3 = ( vec2( iuv.x + h1x, iuv.y + h1y ) - 0.5 ) * texelSize.xy;
		return g0( fuv.y ) * ( g0x * textureLod( tex, p0, lod ) + g1x * textureLod( tex, p1, lod ) ) +
			g1( fuv.y ) * ( g0x * textureLod( tex, p2, lod ) + g1x * textureLod( tex, p3, lod ) );
	}
	vec4 textureBicubic( sampler2D sampler, vec2 uv, float lod ) {
		vec2 fLodSize = vec2( textureSize( sampler, int( lod ) ) );
		vec2 cLodSize = vec2( textureSize( sampler, int( lod + 1.0 ) ) );
		vec2 fLodSizeInv = 1.0 / fLodSize;
		vec2 cLodSizeInv = 1.0 / cLodSize;
		vec4 fSample = bicubic( sampler, uv, vec4( fLodSizeInv, fLodSize ), floor( lod ) );
		vec4 cSample = bicubic( sampler, uv, vec4( cLodSizeInv, cLodSize ), ceil( lod ) );
		return mix( fSample, cSample, fract( lod ) );
	}
	vec3 getVolumeTransmissionRay( const in vec3 n, const in vec3 v, const in float thickness, const in float ior, const in mat4 modelMatrix ) {
		vec3 refractionVector = refract( - v, normalize( n ), 1.0 / ior );
		vec3 modelScale;
		modelScale.x = length( vec3( modelMatrix[ 0 ].xyz ) );
		modelScale.y = length( vec3( modelMatrix[ 1 ].xyz ) );
		modelScale.z = length( vec3( modelMatrix[ 2 ].xyz ) );
		return normalize( refractionVector ) * thickness * modelScale;
	}
	float applyIorToRoughness( const in float roughness, const in float ior ) {
		return roughness * clamp( ior * 2.0 - 2.0, 0.0, 1.0 );
	}
	vec4 getTransmissionSample( const in vec2 fragCoord, const in float roughness, const in float ior ) {
		float lod = log2( transmissionSamplerSize.x ) * applyIorToRoughness( roughness, ior );
		return textureBicubic( transmissionSamplerMap, fragCoord.xy, lod );
	}
	vec3 volumeAttenuation( const in float transmissionDistance, const in vec3 attenuationColor, const in float attenuationDistance ) {
		if ( isinf( attenuationDistance ) ) {
			return vec3( 1.0 );
		} else {
			vec3 attenuationCoefficient = -log( attenuationColor ) / attenuationDistance;
			vec3 transmittance = exp( - attenuationCoefficient * transmissionDistance );			return transmittance;
		}
	}
	vec4 getIBLVolumeRefraction( const in vec3 n, const in vec3 v, const in float roughness, const in vec3 diffuseColor,
		const in vec3 specularColor, const in float specularF90, const in vec3 position, const in mat4 modelMatrix,
		const in mat4 viewMatrix, const in mat4 projMatrix, const in float dispersion, const in float ior, const in float thickness,
		const in vec3 attenuationColor, const in float attenuationDistance ) {
		vec4 transmittedLight;
		vec3 transmittance;
		#ifdef USE_DISPERSION
			float halfSpread = ( ior - 1.0 ) * 0.025 * dispersion;
			vec3 iors = vec3( ior - halfSpread, ior, ior + halfSpread );
			for ( int i = 0; i < 3; i ++ ) {
				vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, iors[ i ], modelMatrix );
				vec3 refractedRayExit = position + transmissionRay;
				vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
				vec2 refractionCoords = ndcPos.xy / ndcPos.w;
				refractionCoords += 1.0;
				refractionCoords /= 2.0;
				vec4 transmissionSample = getTransmissionSample( refractionCoords, roughness, iors[ i ] );
				transmittedLight[ i ] = transmissionSample[ i ];
				transmittedLight.a += transmissionSample.a;
				transmittance[ i ] = diffuseColor[ i ] * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance )[ i ];
			}
			transmittedLight.a /= 3.0;
		#else
			vec3 transmissionRay = getVolumeTransmissionRay( n, v, thickness, ior, modelMatrix );
			vec3 refractedRayExit = position + transmissionRay;
			vec4 ndcPos = projMatrix * viewMatrix * vec4( refractedRayExit, 1.0 );
			vec2 refractionCoords = ndcPos.xy / ndcPos.w;
			refractionCoords += 1.0;
			refractionCoords /= 2.0;
			transmittedLight = getTransmissionSample( refractionCoords, roughness, ior );
			transmittance = diffuseColor * volumeAttenuation( length( transmissionRay ), attenuationColor, attenuationDistance );
		#endif
		vec3 attenuatedColor = transmittance * transmittedLight.rgb;
		vec3 F = EnvironmentBRDF( n, v, specularColor, specularF90, roughness );
		float transmittanceFactor = ( transmittance.r + transmittance.g + transmittance.b ) / 3.0;
		return vec4( ( 1.0 - F ) * attenuatedColor, 1.0 - ( 1.0 - transmittedLight.a ) * transmittanceFactor );
	}
#endif`,E_=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_SPECULARMAP
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,T_=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	varying vec2 vUv;
#endif
#ifdef USE_MAP
	uniform mat3 mapTransform;
	varying vec2 vMapUv;
#endif
#ifdef USE_ALPHAMAP
	uniform mat3 alphaMapTransform;
	varying vec2 vAlphaMapUv;
#endif
#ifdef USE_LIGHTMAP
	uniform mat3 lightMapTransform;
	varying vec2 vLightMapUv;
#endif
#ifdef USE_AOMAP
	uniform mat3 aoMapTransform;
	varying vec2 vAoMapUv;
#endif
#ifdef USE_BUMPMAP
	uniform mat3 bumpMapTransform;
	varying vec2 vBumpMapUv;
#endif
#ifdef USE_NORMALMAP
	uniform mat3 normalMapTransform;
	varying vec2 vNormalMapUv;
#endif
#ifdef USE_DISPLACEMENTMAP
	uniform mat3 displacementMapTransform;
	varying vec2 vDisplacementMapUv;
#endif
#ifdef USE_EMISSIVEMAP
	uniform mat3 emissiveMapTransform;
	varying vec2 vEmissiveMapUv;
#endif
#ifdef USE_METALNESSMAP
	uniform mat3 metalnessMapTransform;
	varying vec2 vMetalnessMapUv;
#endif
#ifdef USE_ROUGHNESSMAP
	uniform mat3 roughnessMapTransform;
	varying vec2 vRoughnessMapUv;
#endif
#ifdef USE_ANISOTROPYMAP
	uniform mat3 anisotropyMapTransform;
	varying vec2 vAnisotropyMapUv;
#endif
#ifdef USE_CLEARCOATMAP
	uniform mat3 clearcoatMapTransform;
	varying vec2 vClearcoatMapUv;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	uniform mat3 clearcoatNormalMapTransform;
	varying vec2 vClearcoatNormalMapUv;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	uniform mat3 clearcoatRoughnessMapTransform;
	varying vec2 vClearcoatRoughnessMapUv;
#endif
#ifdef USE_SHEEN_COLORMAP
	uniform mat3 sheenColorMapTransform;
	varying vec2 vSheenColorMapUv;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	uniform mat3 sheenRoughnessMapTransform;
	varying vec2 vSheenRoughnessMapUv;
#endif
#ifdef USE_IRIDESCENCEMAP
	uniform mat3 iridescenceMapTransform;
	varying vec2 vIridescenceMapUv;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	uniform mat3 iridescenceThicknessMapTransform;
	varying vec2 vIridescenceThicknessMapUv;
#endif
#ifdef USE_SPECULARMAP
	uniform mat3 specularMapTransform;
	varying vec2 vSpecularMapUv;
#endif
#ifdef USE_SPECULAR_COLORMAP
	uniform mat3 specularColorMapTransform;
	varying vec2 vSpecularColorMapUv;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	uniform mat3 specularIntensityMapTransform;
	varying vec2 vSpecularIntensityMapUv;
#endif
#ifdef USE_TRANSMISSIONMAP
	uniform mat3 transmissionMapTransform;
	varying vec2 vTransmissionMapUv;
#endif
#ifdef USE_THICKNESSMAP
	uniform mat3 thicknessMapTransform;
	varying vec2 vThicknessMapUv;
#endif`,A_=`#if defined( USE_UV ) || defined( USE_ANISOTROPY )
	vUv = vec3( uv, 1 ).xy;
#endif
#ifdef USE_MAP
	vMapUv = ( mapTransform * vec3( MAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ALPHAMAP
	vAlphaMapUv = ( alphaMapTransform * vec3( ALPHAMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_LIGHTMAP
	vLightMapUv = ( lightMapTransform * vec3( LIGHTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_AOMAP
	vAoMapUv = ( aoMapTransform * vec3( AOMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_BUMPMAP
	vBumpMapUv = ( bumpMapTransform * vec3( BUMPMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_NORMALMAP
	vNormalMapUv = ( normalMapTransform * vec3( NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_DISPLACEMENTMAP
	vDisplacementMapUv = ( displacementMapTransform * vec3( DISPLACEMENTMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_EMISSIVEMAP
	vEmissiveMapUv = ( emissiveMapTransform * vec3( EMISSIVEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_METALNESSMAP
	vMetalnessMapUv = ( metalnessMapTransform * vec3( METALNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ROUGHNESSMAP
	vRoughnessMapUv = ( roughnessMapTransform * vec3( ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_ANISOTROPYMAP
	vAnisotropyMapUv = ( anisotropyMapTransform * vec3( ANISOTROPYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOATMAP
	vClearcoatMapUv = ( clearcoatMapTransform * vec3( CLEARCOATMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_NORMALMAP
	vClearcoatNormalMapUv = ( clearcoatNormalMapTransform * vec3( CLEARCOAT_NORMALMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_CLEARCOAT_ROUGHNESSMAP
	vClearcoatRoughnessMapUv = ( clearcoatRoughnessMapTransform * vec3( CLEARCOAT_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCEMAP
	vIridescenceMapUv = ( iridescenceMapTransform * vec3( IRIDESCENCEMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_IRIDESCENCE_THICKNESSMAP
	vIridescenceThicknessMapUv = ( iridescenceThicknessMapTransform * vec3( IRIDESCENCE_THICKNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_COLORMAP
	vSheenColorMapUv = ( sheenColorMapTransform * vec3( SHEEN_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SHEEN_ROUGHNESSMAP
	vSheenRoughnessMapUv = ( sheenRoughnessMapTransform * vec3( SHEEN_ROUGHNESSMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULARMAP
	vSpecularMapUv = ( specularMapTransform * vec3( SPECULARMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_COLORMAP
	vSpecularColorMapUv = ( specularColorMapTransform * vec3( SPECULAR_COLORMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_SPECULAR_INTENSITYMAP
	vSpecularIntensityMapUv = ( specularIntensityMapTransform * vec3( SPECULAR_INTENSITYMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_TRANSMISSIONMAP
	vTransmissionMapUv = ( transmissionMapTransform * vec3( TRANSMISSIONMAP_UV, 1 ) ).xy;
#endif
#ifdef USE_THICKNESSMAP
	vThicknessMapUv = ( thicknessMapTransform * vec3( THICKNESSMAP_UV, 1 ) ).xy;
#endif`,R_=`#if defined( USE_ENVMAP ) || defined( DISTANCE ) || defined ( USE_SHADOWMAP ) || defined ( USE_TRANSMISSION ) || NUM_SPOT_LIGHT_COORDS > 0
	vec4 worldPosition = vec4( transformed, 1.0 );
	#ifdef USE_BATCHING
		worldPosition = batchingMatrix * worldPosition;
	#endif
	#ifdef USE_INSTANCING
		worldPosition = instanceMatrix * worldPosition;
	#endif
	worldPosition = modelMatrix * worldPosition;
#endif`;const C_=`varying vec2 vUv;
uniform mat3 uvTransform;
void main() {
	vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	gl_Position = vec4( position.xy, 1.0, 1.0 );
}`,P_=`uniform sampler2D t2D;
uniform float backgroundIntensity;
varying vec2 vUv;
void main() {
	vec4 texColor = texture2D( t2D, vUv );
	#ifdef DECODE_VIDEO_TEXTURE
		texColor = vec4( mix( pow( texColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), texColor.rgb * 0.0773993808, vec3( lessThanEqual( texColor.rgb, vec3( 0.04045 ) ) ) ), texColor.w );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,I_=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,L_=`#ifdef ENVMAP_TYPE_CUBE
	uniform samplerCube envMap;
#elif defined( ENVMAP_TYPE_CUBE_UV )
	uniform sampler2D envMap;
#endif
uniform float flipEnvMap;
uniform float backgroundBlurriness;
uniform float backgroundIntensity;
uniform mat3 backgroundRotation;
varying vec3 vWorldDirection;
#include <cube_uv_reflection_fragment>
void main() {
	#ifdef ENVMAP_TYPE_CUBE
		vec4 texColor = textureCube( envMap, backgroundRotation * vec3( flipEnvMap * vWorldDirection.x, vWorldDirection.yz ) );
	#elif defined( ENVMAP_TYPE_CUBE_UV )
		vec4 texColor = textureCubeUV( envMap, backgroundRotation * vWorldDirection, backgroundBlurriness );
	#else
		vec4 texColor = vec4( 0.0, 0.0, 0.0, 1.0 );
	#endif
	texColor.rgb *= backgroundIntensity;
	gl_FragColor = texColor;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,D_=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
	gl_Position.z = gl_Position.w;
}`,N_=`uniform samplerCube tCube;
uniform float tFlip;
uniform float opacity;
varying vec3 vWorldDirection;
void main() {
	vec4 texColor = textureCube( tCube, vec3( tFlip * vWorldDirection.x, vWorldDirection.yz ) );
	gl_FragColor = texColor;
	gl_FragColor.a *= opacity;
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,U_=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
varying vec2 vHighPrecisionZW;
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vHighPrecisionZW = gl_Position.zw;
}`,F_=`#if DEPTH_PACKING == 3200
	uniform float opacity;
#endif
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
varying vec2 vHighPrecisionZW;
void main() {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#if DEPTH_PACKING == 3200
		diffuseColor.a = opacity;
	#endif
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <logdepthbuf_fragment>
	#ifdef USE_REVERSEDEPTHBUF
		float fragCoordZ = vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ];
	#else
		float fragCoordZ = 0.5 * vHighPrecisionZW[ 0 ] / vHighPrecisionZW[ 1 ] + 0.5;
	#endif
	#if DEPTH_PACKING == 3200
		gl_FragColor = vec4( vec3( 1.0 - fragCoordZ ), opacity );
	#elif DEPTH_PACKING == 3201
		gl_FragColor = packDepthToRGBA( fragCoordZ );
	#elif DEPTH_PACKING == 3202
		gl_FragColor = vec4( packDepthToRGB( fragCoordZ ), 1.0 );
	#elif DEPTH_PACKING == 3203
		gl_FragColor = vec4( packDepthToRG( fragCoordZ ), 0.0, 1.0 );
	#endif
}`,O_=`#define DISTANCE
varying vec3 vWorldPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <skinbase_vertex>
	#include <morphinstance_vertex>
	#ifdef USE_DISPLACEMENTMAP
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <worldpos_vertex>
	#include <clipping_planes_vertex>
	vWorldPosition = worldPosition.xyz;
}`,B_=`#define DISTANCE
uniform vec3 referencePosition;
uniform float nearDistance;
uniform float farDistance;
varying vec3 vWorldPosition;
#include <common>
#include <packing>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <clipping_planes_pars_fragment>
void main () {
	vec4 diffuseColor = vec4( 1.0 );
	#include <clipping_planes_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	float dist = length( vWorldPosition - referencePosition );
	dist = ( dist - nearDistance ) / ( farDistance - nearDistance );
	dist = saturate( dist );
	gl_FragColor = packDepthToRGBA( dist );
}`,z_=`varying vec3 vWorldDirection;
#include <common>
void main() {
	vWorldDirection = transformDirection( position, modelMatrix );
	#include <begin_vertex>
	#include <project_vertex>
}`,k_=`uniform sampler2D tEquirect;
varying vec3 vWorldDirection;
#include <common>
void main() {
	vec3 direction = normalize( vWorldDirection );
	vec2 sampleUV = equirectUv( direction );
	gl_FragColor = texture2D( tEquirect, sampleUV );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
}`,H_=`uniform float scale;
attribute float lineDistance;
varying float vLineDistance;
#include <common>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	vLineDistance = scale * lineDistance;
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,G_=`uniform vec3 diffuse;
uniform float opacity;
uniform float dashSize;
uniform float totalSize;
varying float vLineDistance;
#include <common>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	if ( mod( vLineDistance, totalSize ) > dashSize ) {
		discard;
	}
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,V_=`#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#if defined ( USE_ENVMAP ) || defined ( USE_SKINNING )
		#include <beginnormal_vertex>
		#include <morphnormal_vertex>
		#include <skinbase_vertex>
		#include <skinnormal_vertex>
		#include <defaultnormal_vertex>
	#endif
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <fog_vertex>
}`,W_=`uniform vec3 diffuse;
uniform float opacity;
#ifndef FLAT_SHADED
	varying vec3 vNormal;
#endif
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	#ifdef USE_LIGHTMAP
		vec4 lightMapTexel = texture2D( lightMap, vLightMapUv );
		reflectedLight.indirectDiffuse += lightMapTexel.rgb * lightMapIntensity * RECIPROCAL_PI;
	#else
		reflectedLight.indirectDiffuse += vec3( 1.0 );
	#endif
	#include <aomap_fragment>
	reflectedLight.indirectDiffuse *= diffuseColor.rgb;
	vec3 outgoingLight = reflectedLight.indirectDiffuse;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,X_=`#define LAMBERT
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,j_=`#define LAMBERT
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_lambert_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_lambert_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,q_=`#define MATCAP
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <color_pars_vertex>
#include <displacementmap_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
	vViewPosition = - mvPosition.xyz;
}`,Y_=`#define MATCAP
uniform vec3 diffuse;
uniform float opacity;
uniform sampler2D matcap;
varying vec3 vViewPosition;
#include <common>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	vec3 viewDir = normalize( vViewPosition );
	vec3 x = normalize( vec3( viewDir.z, 0.0, - viewDir.x ) );
	vec3 y = cross( viewDir, x );
	vec2 uv = vec2( dot( x, normal ), dot( y, normal ) ) * 0.495 + 0.5;
	#ifdef USE_MATCAP
		vec4 matcapColor = texture2D( matcap, uv );
	#else
		vec4 matcapColor = vec4( vec3( mix( 0.2, 0.8, uv.y ) ), 1.0 );
	#endif
	vec3 outgoingLight = diffuseColor.rgb * matcapColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,K_=`#define NORMAL
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	vViewPosition = - mvPosition.xyz;
#endif
}`,$_=`#define NORMAL
uniform float opacity;
#if defined( FLAT_SHADED ) || defined( USE_BUMPMAP ) || defined( USE_NORMALMAP_TANGENTSPACE )
	varying vec3 vViewPosition;
#endif
#include <packing>
#include <uv_pars_fragment>
#include <normal_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( 0.0, 0.0, 0.0, opacity );
	#include <clipping_planes_fragment>
	#include <logdepthbuf_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	gl_FragColor = vec4( packNormalToRGB( normal ), diffuseColor.a );
	#ifdef OPAQUE
		gl_FragColor.a = 1.0;
	#endif
}`,Z_=`#define PHONG
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <envmap_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,J_=`#define PHONG
uniform vec3 diffuse;
uniform vec3 emissive;
uniform vec3 specular;
uniform float shininess;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_phong_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <specularmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_phong_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + reflectedLight.directSpecular + reflectedLight.indirectSpecular + totalEmissiveRadiance;
	#include <envmap_fragment>
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,Q_=`#define STANDARD
varying vec3 vViewPosition;
#ifdef USE_TRANSMISSION
	varying vec3 vWorldPosition;
#endif
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
#ifdef USE_TRANSMISSION
	vWorldPosition = worldPosition.xyz;
#endif
}`,e0=`#define STANDARD
#ifdef PHYSICAL
	#define IOR
	#define USE_SPECULAR
#endif
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float roughness;
uniform float metalness;
uniform float opacity;
#ifdef IOR
	uniform float ior;
#endif
#ifdef USE_SPECULAR
	uniform float specularIntensity;
	uniform vec3 specularColor;
	#ifdef USE_SPECULAR_COLORMAP
		uniform sampler2D specularColorMap;
	#endif
	#ifdef USE_SPECULAR_INTENSITYMAP
		uniform sampler2D specularIntensityMap;
	#endif
#endif
#ifdef USE_CLEARCOAT
	uniform float clearcoat;
	uniform float clearcoatRoughness;
#endif
#ifdef USE_DISPERSION
	uniform float dispersion;
#endif
#ifdef USE_IRIDESCENCE
	uniform float iridescence;
	uniform float iridescenceIOR;
	uniform float iridescenceThicknessMinimum;
	uniform float iridescenceThicknessMaximum;
#endif
#ifdef USE_SHEEN
	uniform vec3 sheenColor;
	uniform float sheenRoughness;
	#ifdef USE_SHEEN_COLORMAP
		uniform sampler2D sheenColorMap;
	#endif
	#ifdef USE_SHEEN_ROUGHNESSMAP
		uniform sampler2D sheenRoughnessMap;
	#endif
#endif
#ifdef USE_ANISOTROPY
	uniform vec2 anisotropyVector;
	#ifdef USE_ANISOTROPYMAP
		uniform sampler2D anisotropyMap;
	#endif
#endif
varying vec3 vViewPosition;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <iridescence_fragment>
#include <cube_uv_reflection_fragment>
#include <envmap_common_pars_fragment>
#include <envmap_physical_pars_fragment>
#include <fog_pars_fragment>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_physical_pars_fragment>
#include <transmission_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <clearcoat_pars_fragment>
#include <iridescence_pars_fragment>
#include <roughnessmap_pars_fragment>
#include <metalnessmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <roughnessmap_fragment>
	#include <metalnessmap_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <clearcoat_normal_fragment_begin>
	#include <clearcoat_normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_physical_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 totalDiffuse = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;
	vec3 totalSpecular = reflectedLight.directSpecular + reflectedLight.indirectSpecular;
	#include <transmission_fragment>
	vec3 outgoingLight = totalDiffuse + totalSpecular + totalEmissiveRadiance;
	#ifdef USE_SHEEN
		float sheenEnergyComp = 1.0 - 0.157 * max3( material.sheenColor );
		outgoingLight = outgoingLight * sheenEnergyComp + sheenSpecularDirect + sheenSpecularIndirect;
	#endif
	#ifdef USE_CLEARCOAT
		float dotNVcc = saturate( dot( geometryClearcoatNormal, geometryViewDir ) );
		vec3 Fcc = F_Schlick( material.clearcoatF0, material.clearcoatF90, dotNVcc );
		outgoingLight = outgoingLight * ( 1.0 - material.clearcoat * Fcc ) + ( clearcoatSpecularDirect + clearcoatSpecularIndirect ) * material.clearcoat;
	#endif
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,t0=`#define TOON
varying vec3 vViewPosition;
#include <common>
#include <batching_pars_vertex>
#include <uv_pars_vertex>
#include <displacementmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <normal_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <normal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <displacementmap_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	vViewPosition = - mvPosition.xyz;
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,n0=`#define TOON
uniform vec3 diffuse;
uniform vec3 emissive;
uniform float opacity;
#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <aomap_pars_fragment>
#include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>
#include <gradientmap_pars_fragment>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <normal_pars_fragment>
#include <lights_toon_pars_fragment>
#include <shadowmap_pars_fragment>
#include <bumpmap_pars_fragment>
#include <normalmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
	vec3 totalEmissiveRadiance = emissive;
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <color_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	#include <normal_fragment_begin>
	#include <normal_fragment_maps>
	#include <emissivemap_fragment>
	#include <lights_toon_fragment>
	#include <lights_fragment_begin>
	#include <lights_fragment_maps>
	#include <lights_fragment_end>
	#include <aomap_fragment>
	vec3 outgoingLight = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse + totalEmissiveRadiance;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
	#include <dithering_fragment>
}`,i0=`uniform float size;
uniform float scale;
#include <common>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
#ifdef USE_POINTS_UV
	varying vec2 vUv;
	uniform mat3 uvTransform;
#endif
void main() {
	#ifdef USE_POINTS_UV
		vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
	#endif
	#include <color_vertex>
	#include <morphinstance_vertex>
	#include <morphcolor_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <project_vertex>
	gl_PointSize = size;
	#ifdef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) gl_PointSize *= ( scale / - mvPosition.z );
	#endif
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <worldpos_vertex>
	#include <fog_vertex>
}`,r0=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <color_pars_fragment>
#include <map_particle_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_particle_fragment>
	#include <color_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
	#include <premultiplied_alpha_fragment>
}`,s0=`#include <common>
#include <batching_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <shadowmap_pars_vertex>
void main() {
	#include <batching_vertex>
	#include <beginnormal_vertex>
	#include <morphinstance_vertex>
	#include <morphnormal_vertex>
	#include <skinbase_vertex>
	#include <skinnormal_vertex>
	#include <defaultnormal_vertex>
	#include <begin_vertex>
	#include <morphtarget_vertex>
	#include <skinning_vertex>
	#include <project_vertex>
	#include <logdepthbuf_vertex>
	#include <worldpos_vertex>
	#include <shadowmap_vertex>
	#include <fog_vertex>
}`,a0=`uniform vec3 color;
uniform float opacity;
#include <common>
#include <packing>
#include <fog_pars_fragment>
#include <bsdfs>
#include <lights_pars_begin>
#include <logdepthbuf_pars_fragment>
#include <shadowmap_pars_fragment>
#include <shadowmask_pars_fragment>
void main() {
	#include <logdepthbuf_fragment>
	gl_FragColor = vec4( color, opacity * ( 1.0 - getShadowMask() ) );
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`,o0=`uniform float rotation;
uniform vec2 center;
#include <common>
#include <uv_pars_vertex>
#include <fog_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>
void main() {
	#include <uv_vertex>
	vec4 mvPosition = modelViewMatrix[ 3 ];
	vec2 scale = vec2( length( modelMatrix[ 0 ].xyz ), length( modelMatrix[ 1 ].xyz ) );
	#ifndef USE_SIZEATTENUATION
		bool isPerspective = isPerspectiveMatrix( projectionMatrix );
		if ( isPerspective ) scale *= - mvPosition.z;
	#endif
	vec2 alignedPosition = ( position.xy - ( center - vec2( 0.5 ) ) ) * scale;
	vec2 rotatedPosition;
	rotatedPosition.x = cos( rotation ) * alignedPosition.x - sin( rotation ) * alignedPosition.y;
	rotatedPosition.y = sin( rotation ) * alignedPosition.x + cos( rotation ) * alignedPosition.y;
	mvPosition.xy += rotatedPosition;
	gl_Position = projectionMatrix * mvPosition;
	#include <logdepthbuf_vertex>
	#include <clipping_planes_vertex>
	#include <fog_vertex>
}`,l0=`uniform vec3 diffuse;
uniform float opacity;
#include <common>
#include <uv_pars_fragment>
#include <map_pars_fragment>
#include <alphamap_pars_fragment>
#include <alphatest_pars_fragment>
#include <alphahash_pars_fragment>
#include <fog_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>
void main() {
	vec4 diffuseColor = vec4( diffuse, opacity );
	#include <clipping_planes_fragment>
	vec3 outgoingLight = vec3( 0.0 );
	#include <logdepthbuf_fragment>
	#include <map_fragment>
	#include <alphamap_fragment>
	#include <alphatest_fragment>
	#include <alphahash_fragment>
	outgoingLight = diffuseColor.rgb;
	#include <opaque_fragment>
	#include <tonemapping_fragment>
	#include <colorspace_fragment>
	#include <fog_fragment>
}`,We={alphahash_fragment:Pm,alphahash_pars_fragment:Im,alphamap_fragment:Lm,alphamap_pars_fragment:Dm,alphatest_fragment:Nm,alphatest_pars_fragment:Um,aomap_fragment:Fm,aomap_pars_fragment:Om,batching_pars_vertex:Bm,batching_vertex:zm,begin_vertex:km,beginnormal_vertex:Hm,bsdfs:Gm,iridescence_fragment:Vm,bumpmap_pars_fragment:Wm,clipping_planes_fragment:Xm,clipping_planes_pars_fragment:jm,clipping_planes_pars_vertex:qm,clipping_planes_vertex:Ym,color_fragment:Km,color_pars_fragment:$m,color_pars_vertex:Zm,color_vertex:Jm,common:Qm,cube_uv_reflection_fragment:eg,defaultnormal_vertex:tg,displacementmap_pars_vertex:ng,displacementmap_vertex:ig,emissivemap_fragment:rg,emissivemap_pars_fragment:sg,colorspace_fragment:ag,colorspace_pars_fragment:og,envmap_fragment:lg,envmap_common_pars_fragment:cg,envmap_pars_fragment:dg,envmap_pars_vertex:ug,envmap_physical_pars_fragment:bg,envmap_vertex:hg,fog_vertex:fg,fog_pars_vertex:pg,fog_fragment:mg,fog_pars_fragment:gg,gradientmap_pars_fragment:_g,lightmap_pars_fragment:yg,lights_lambert_fragment:xg,lights_lambert_pars_fragment:vg,lights_pars_begin:Mg,lights_toon_fragment:Sg,lights_toon_pars_fragment:wg,lights_phong_fragment:Eg,lights_phong_pars_fragment:Tg,lights_physical_fragment:Ag,lights_physical_pars_fragment:Rg,lights_fragment_begin:Cg,lights_fragment_maps:Pg,lights_fragment_end:Ig,logdepthbuf_fragment:Lg,logdepthbuf_pars_fragment:Dg,logdepthbuf_pars_vertex:Ng,logdepthbuf_vertex:Ug,map_fragment:Fg,map_pars_fragment:Og,map_particle_fragment:Bg,map_particle_pars_fragment:zg,metalnessmap_fragment:kg,metalnessmap_pars_fragment:Hg,morphinstance_vertex:Gg,morphcolor_vertex:Vg,morphnormal_vertex:Wg,morphtarget_pars_vertex:Xg,morphtarget_vertex:jg,normal_fragment_begin:qg,normal_fragment_maps:Yg,normal_pars_fragment:Kg,normal_pars_vertex:$g,normal_vertex:Zg,normalmap_pars_fragment:Jg,clearcoat_normal_fragment_begin:Qg,clearcoat_normal_fragment_maps:e_,clearcoat_pars_fragment:t_,iridescence_pars_fragment:n_,opaque_fragment:i_,packing:r_,premultiplied_alpha_fragment:s_,project_vertex:a_,dithering_fragment:o_,dithering_pars_fragment:l_,roughnessmap_fragment:c_,roughnessmap_pars_fragment:d_,shadowmap_pars_fragment:u_,shadowmap_pars_vertex:h_,shadowmap_vertex:f_,shadowmask_pars_fragment:p_,skinbase_vertex:m_,skinning_pars_vertex:g_,skinning_vertex:__,skinnormal_vertex:y_,specularmap_fragment:x_,specularmap_pars_fragment:v_,tonemapping_fragment:M_,tonemapping_pars_fragment:b_,transmission_fragment:S_,transmission_pars_fragment:w_,uv_pars_fragment:E_,uv_pars_vertex:T_,uv_vertex:A_,worldpos_vertex:R_,background_vert:C_,background_frag:P_,backgroundCube_vert:I_,backgroundCube_frag:L_,cube_vert:D_,cube_frag:N_,depth_vert:U_,depth_frag:F_,distanceRGBA_vert:O_,distanceRGBA_frag:B_,equirect_vert:z_,equirect_frag:k_,linedashed_vert:H_,linedashed_frag:G_,meshbasic_vert:V_,meshbasic_frag:W_,meshlambert_vert:X_,meshlambert_frag:j_,meshmatcap_vert:q_,meshmatcap_frag:Y_,meshnormal_vert:K_,meshnormal_frag:$_,meshphong_vert:Z_,meshphong_frag:J_,meshphysical_vert:Q_,meshphysical_frag:e0,meshtoon_vert:t0,meshtoon_frag:n0,points_vert:i0,points_frag:r0,shadow_vert:s0,shadow_frag:a0,sprite_vert:o0,sprite_frag:l0},ce={common:{diffuse:{value:new Ee(16777215)},opacity:{value:1},map:{value:null},mapTransform:{value:new Ve},alphaMap:{value:null},alphaMapTransform:{value:new Ve},alphaTest:{value:0}},specularmap:{specularMap:{value:null},specularMapTransform:{value:new Ve}},envmap:{envMap:{value:null},envMapRotation:{value:new Ve},flipEnvMap:{value:-1},reflectivity:{value:1},ior:{value:1.5},refractionRatio:{value:.98}},aomap:{aoMap:{value:null},aoMapIntensity:{value:1},aoMapTransform:{value:new Ve}},lightmap:{lightMap:{value:null},lightMapIntensity:{value:1},lightMapTransform:{value:new Ve}},bumpmap:{bumpMap:{value:null},bumpMapTransform:{value:new Ve},bumpScale:{value:1}},normalmap:{normalMap:{value:null},normalMapTransform:{value:new Ve},normalScale:{value:new xe(1,1)}},displacementmap:{displacementMap:{value:null},displacementMapTransform:{value:new Ve},displacementScale:{value:1},displacementBias:{value:0}},emissivemap:{emissiveMap:{value:null},emissiveMapTransform:{value:new Ve}},metalnessmap:{metalnessMap:{value:null},metalnessMapTransform:{value:new Ve}},roughnessmap:{roughnessMap:{value:null},roughnessMapTransform:{value:new Ve}},gradientmap:{gradientMap:{value:null}},fog:{fogDensity:{value:25e-5},fogNear:{value:1},fogFar:{value:2e3},fogColor:{value:new Ee(16777215)}},lights:{ambientLightColor:{value:[]},lightProbe:{value:[]},directionalLights:{value:[],properties:{direction:{},color:{}}},directionalLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},directionalShadowMap:{value:[]},directionalShadowMatrix:{value:[]},spotLights:{value:[],properties:{color:{},position:{},direction:{},distance:{},coneCos:{},penumbraCos:{},decay:{}}},spotLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{}}},spotLightMap:{value:[]},spotShadowMap:{value:[]},spotLightMatrix:{value:[]},pointLights:{value:[],properties:{color:{},position:{},decay:{},distance:{}}},pointLightShadows:{value:[],properties:{shadowIntensity:1,shadowBias:{},shadowNormalBias:{},shadowRadius:{},shadowMapSize:{},shadowCameraNear:{},shadowCameraFar:{}}},pointShadowMap:{value:[]},pointShadowMatrix:{value:[]},hemisphereLights:{value:[],properties:{direction:{},skyColor:{},groundColor:{}}},rectAreaLights:{value:[],properties:{color:{},position:{},width:{},height:{}}},ltc_1:{value:null},ltc_2:{value:null}},points:{diffuse:{value:new Ee(16777215)},opacity:{value:1},size:{value:1},scale:{value:1},map:{value:null},alphaMap:{value:null},alphaMapTransform:{value:new Ve},alphaTest:{value:0},uvTransform:{value:new Ve}},sprite:{diffuse:{value:new Ee(16777215)},opacity:{value:1},center:{value:new xe(.5,.5)},rotation:{value:0},map:{value:null},mapTransform:{value:new Ve},alphaMap:{value:null},alphaMapTransform:{value:new Ve},alphaTest:{value:0}}},Rn={basic:{uniforms:Vt([ce.common,ce.specularmap,ce.envmap,ce.aomap,ce.lightmap,ce.fog]),vertexShader:We.meshbasic_vert,fragmentShader:We.meshbasic_frag},lambert:{uniforms:Vt([ce.common,ce.specularmap,ce.envmap,ce.aomap,ce.lightmap,ce.emissivemap,ce.bumpmap,ce.normalmap,ce.displacementmap,ce.fog,ce.lights,{emissive:{value:new Ee(0)}}]),vertexShader:We.meshlambert_vert,fragmentShader:We.meshlambert_frag},phong:{uniforms:Vt([ce.common,ce.specularmap,ce.envmap,ce.aomap,ce.lightmap,ce.emissivemap,ce.bumpmap,ce.normalmap,ce.displacementmap,ce.fog,ce.lights,{emissive:{value:new Ee(0)},specular:{value:new Ee(1118481)},shininess:{value:30}}]),vertexShader:We.meshphong_vert,fragmentShader:We.meshphong_frag},standard:{uniforms:Vt([ce.common,ce.envmap,ce.aomap,ce.lightmap,ce.emissivemap,ce.bumpmap,ce.normalmap,ce.displacementmap,ce.roughnessmap,ce.metalnessmap,ce.fog,ce.lights,{emissive:{value:new Ee(0)},roughness:{value:1},metalness:{value:0},envMapIntensity:{value:1}}]),vertexShader:We.meshphysical_vert,fragmentShader:We.meshphysical_frag},toon:{uniforms:Vt([ce.common,ce.aomap,ce.lightmap,ce.emissivemap,ce.bumpmap,ce.normalmap,ce.displacementmap,ce.gradientmap,ce.fog,ce.lights,{emissive:{value:new Ee(0)}}]),vertexShader:We.meshtoon_vert,fragmentShader:We.meshtoon_frag},matcap:{uniforms:Vt([ce.common,ce.bumpmap,ce.normalmap,ce.displacementmap,ce.fog,{matcap:{value:null}}]),vertexShader:We.meshmatcap_vert,fragmentShader:We.meshmatcap_frag},points:{uniforms:Vt([ce.points,ce.fog]),vertexShader:We.points_vert,fragmentShader:We.points_frag},dashed:{uniforms:Vt([ce.common,ce.fog,{scale:{value:1},dashSize:{value:1},totalSize:{value:2}}]),vertexShader:We.linedashed_vert,fragmentShader:We.linedashed_frag},depth:{uniforms:Vt([ce.common,ce.displacementmap]),vertexShader:We.depth_vert,fragmentShader:We.depth_frag},normal:{uniforms:Vt([ce.common,ce.bumpmap,ce.normalmap,ce.displacementmap,{opacity:{value:1}}]),vertexShader:We.meshnormal_vert,fragmentShader:We.meshnormal_frag},sprite:{uniforms:Vt([ce.sprite,ce.fog]),vertexShader:We.sprite_vert,fragmentShader:We.sprite_frag},background:{uniforms:{uvTransform:{value:new Ve},t2D:{value:null},backgroundIntensity:{value:1}},vertexShader:We.background_vert,fragmentShader:We.background_frag},backgroundCube:{uniforms:{envMap:{value:null},flipEnvMap:{value:-1},backgroundBlurriness:{value:0},backgroundIntensity:{value:1},backgroundRotation:{value:new Ve}},vertexShader:We.backgroundCube_vert,fragmentShader:We.backgroundCube_frag},cube:{uniforms:{tCube:{value:null},tFlip:{value:-1},opacity:{value:1}},vertexShader:We.cube_vert,fragmentShader:We.cube_frag},equirect:{uniforms:{tEquirect:{value:null}},vertexShader:We.equirect_vert,fragmentShader:We.equirect_frag},distanceRGBA:{uniforms:Vt([ce.common,ce.displacementmap,{referencePosition:{value:new P},nearDistance:{value:1},farDistance:{value:1e3}}]),vertexShader:We.distanceRGBA_vert,fragmentShader:We.distanceRGBA_frag},shadow:{uniforms:Vt([ce.lights,ce.fog,{color:{value:new Ee(0)},opacity:{value:1}}]),vertexShader:We.shadow_vert,fragmentShader:We.shadow_frag}};Rn.physical={uniforms:Vt([Rn.standard.uniforms,{clearcoat:{value:0},clearcoatMap:{value:null},clearcoatMapTransform:{value:new Ve},clearcoatNormalMap:{value:null},clearcoatNormalMapTransform:{value:new Ve},clearcoatNormalScale:{value:new xe(1,1)},clearcoatRoughness:{value:0},clearcoatRoughnessMap:{value:null},clearcoatRoughnessMapTransform:{value:new Ve},dispersion:{value:0},iridescence:{value:0},iridescenceMap:{value:null},iridescenceMapTransform:{value:new Ve},iridescenceIOR:{value:1.3},iridescenceThicknessMinimum:{value:100},iridescenceThicknessMaximum:{value:400},iridescenceThicknessMap:{value:null},iridescenceThicknessMapTransform:{value:new Ve},sheen:{value:0},sheenColor:{value:new Ee(0)},sheenColorMap:{value:null},sheenColorMapTransform:{value:new Ve},sheenRoughness:{value:1},sheenRoughnessMap:{value:null},sheenRoughnessMapTransform:{value:new Ve},transmission:{value:0},transmissionMap:{value:null},transmissionMapTransform:{value:new Ve},transmissionSamplerSize:{value:new xe},transmissionSamplerMap:{value:null},thickness:{value:0},thicknessMap:{value:null},thicknessMapTransform:{value:new Ve},attenuationDistance:{value:0},attenuationColor:{value:new Ee(0)},specularColor:{value:new Ee(1,1,1)},specularColorMap:{value:null},specularColorMapTransform:{value:new Ve},specularIntensity:{value:1},specularIntensityMap:{value:null},specularIntensityMapTransform:{value:new Ve},anisotropyVector:{value:new xe},anisotropyMap:{value:null},anisotropyMapTransform:{value:new Ve}}]),vertexShader:We.meshphysical_vert,fragmentShader:We.meshphysical_frag};const pa={r:0,b:0,g:0},Ei=new pn,c0=new De;function d0(i,e,t,n,r,s,a){const o=new Ee(0);let l=s===!0?0:1,c,h,u=null,f=0,p=null;function _(w){let x=w.isScene===!0?w.background:null;return x&&x.isTexture&&(x=(w.backgroundBlurriness>0?t:e).get(x)),x}function y(w){let x=!1;const T=_(w);T===null?m(o,l):T&&T.isColor&&(m(T,1),x=!0);const L=i.xr.getEnvironmentBlendMode();L==="additive"?n.buffers.color.setClear(0,0,0,1,a):L==="alpha-blend"&&n.buffers.color.setClear(0,0,0,0,a),(i.autoClear||x)&&(n.buffers.depth.setTest(!0),n.buffers.depth.setMask(!0),n.buffers.color.setMask(!0),i.clear(i.autoClearColor,i.autoClearDepth,i.autoClearStencil))}function g(w,x){const T=_(x);T&&(T.isCubeTexture||T.mapping===Va)?(h===void 0&&(h=new ut(new yi(1,1,1),new ti({name:"BackgroundCubeMaterial",uniforms:Tr(Rn.backgroundCube.uniforms),vertexShader:Rn.backgroundCube.vertexShader,fragmentShader:Rn.backgroundCube.fragmentShader,side:jt,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),h.geometry.deleteAttribute("normal"),h.geometry.deleteAttribute("uv"),h.onBeforeRender=function(L,C,R){this.matrixWorld.copyPosition(R.matrixWorld)},Object.defineProperty(h.material,"envMap",{get:function(){return this.uniforms.envMap.value}}),r.update(h)),Ei.copy(x.backgroundRotation),Ei.x*=-1,Ei.y*=-1,Ei.z*=-1,T.isCubeTexture&&T.isRenderTargetTexture===!1&&(Ei.y*=-1,Ei.z*=-1),h.material.uniforms.envMap.value=T,h.material.uniforms.flipEnvMap.value=T.isCubeTexture&&T.isRenderTargetTexture===!1?-1:1,h.material.uniforms.backgroundBlurriness.value=x.backgroundBlurriness,h.material.uniforms.backgroundIntensity.value=x.backgroundIntensity,h.material.uniforms.backgroundRotation.value.setFromMatrix4(c0.makeRotationFromEuler(Ei)),h.material.toneMapped=Je.getTransfer(T.colorSpace)!==lt,(u!==T||f!==T.version||p!==i.toneMapping)&&(h.material.needsUpdate=!0,u=T,f=T.version,p=i.toneMapping),h.layers.enableAll(),w.unshift(h,h.geometry,h.material,0,0,null)):T&&T.isTexture&&(c===void 0&&(c=new ut(new Ss(2,2),new ti({name:"BackgroundMaterial",uniforms:Tr(Rn.background.uniforms),vertexShader:Rn.background.vertexShader,fragmentShader:Rn.background.fragmentShader,side:ei,depthTest:!1,depthWrite:!1,fog:!1,allowOverride:!1})),c.geometry.deleteAttribute("normal"),Object.defineProperty(c.material,"map",{get:function(){return this.uniforms.t2D.value}}),r.update(c)),c.material.uniforms.t2D.value=T,c.material.uniforms.backgroundIntensity.value=x.backgroundIntensity,c.material.toneMapped=Je.getTransfer(T.colorSpace)!==lt,T.matrixAutoUpdate===!0&&T.updateMatrix(),c.material.uniforms.uvTransform.value.copy(T.matrix),(u!==T||f!==T.version||p!==i.toneMapping)&&(c.material.needsUpdate=!0,u=T,f=T.version,p=i.toneMapping),c.layers.enableAll(),w.unshift(c,c.geometry,c.material,0,0,null))}function m(w,x){w.getRGB(pa,Wu(i)),n.buffers.color.setClear(pa.r,pa.g,pa.b,x,a)}function E(){h!==void 0&&(h.geometry.dispose(),h.material.dispose(),h=void 0),c!==void 0&&(c.geometry.dispose(),c.material.dispose(),c=void 0)}return{getClearColor:function(){return o},setClearColor:function(w,x=1){o.set(w),l=x,m(o,l)},getClearAlpha:function(){return l},setClearAlpha:function(w){l=w,m(o,l)},render:y,addToRenderList:g,dispose:E}}function u0(i,e){const t=i.getParameter(i.MAX_VERTEX_ATTRIBS),n={},r=f(null);let s=r,a=!1;function o(b,A,U,z,B){let V=!1;const G=u(z,U,A);s!==G&&(s=G,c(s.object)),V=p(b,z,U,B),V&&_(b,z,U,B),B!==null&&e.update(B,i.ELEMENT_ARRAY_BUFFER),(V||a)&&(a=!1,x(b,A,U,z),B!==null&&i.bindBuffer(i.ELEMENT_ARRAY_BUFFER,e.get(B).buffer))}function l(){return i.createVertexArray()}function c(b){return i.bindVertexArray(b)}function h(b){return i.deleteVertexArray(b)}function u(b,A,U){const z=U.wireframe===!0;let B=n[b.id];B===void 0&&(B={},n[b.id]=B);let V=B[A.id];V===void 0&&(V={},B[A.id]=V);let G=V[z];return G===void 0&&(G=f(l()),V[z]=G),G}function f(b){const A=[],U=[],z=[];for(let B=0;B<t;B++)A[B]=0,U[B]=0,z[B]=0;return{geometry:null,program:null,wireframe:!1,newAttributes:A,enabledAttributes:U,attributeDivisors:z,object:b,attributes:{},index:null}}function p(b,A,U,z){const B=s.attributes,V=A.attributes;let G=0;const J=U.getAttributes();for(const j in J)if(J[j].location>=0){const le=B[j];let Re=V[j];if(Re===void 0&&(j==="instanceMatrix"&&b.instanceMatrix&&(Re=b.instanceMatrix),j==="instanceColor"&&b.instanceColor&&(Re=b.instanceColor)),le===void 0||le.attribute!==Re||Re&&le.data!==Re.data)return!0;G++}return s.attributesNum!==G||s.index!==z}function _(b,A,U,z){const B={},V=A.attributes;let G=0;const J=U.getAttributes();for(const j in J)if(J[j].location>=0){let le=V[j];le===void 0&&(j==="instanceMatrix"&&b.instanceMatrix&&(le=b.instanceMatrix),j==="instanceColor"&&b.instanceColor&&(le=b.instanceColor));const Re={};Re.attribute=le,le&&le.data&&(Re.data=le.data),B[j]=Re,G++}s.attributes=B,s.attributesNum=G,s.index=z}function y(){const b=s.newAttributes;for(let A=0,U=b.length;A<U;A++)b[A]=0}function g(b){m(b,0)}function m(b,A){const U=s.newAttributes,z=s.enabledAttributes,B=s.attributeDivisors;U[b]=1,z[b]===0&&(i.enableVertexAttribArray(b),z[b]=1),B[b]!==A&&(i.vertexAttribDivisor(b,A),B[b]=A)}function E(){const b=s.newAttributes,A=s.enabledAttributes;for(let U=0,z=A.length;U<z;U++)A[U]!==b[U]&&(i.disableVertexAttribArray(U),A[U]=0)}function w(b,A,U,z,B,V,G){G===!0?i.vertexAttribIPointer(b,A,U,B,V):i.vertexAttribPointer(b,A,U,z,B,V)}function x(b,A,U,z){y();const B=z.attributes,V=U.getAttributes(),G=A.defaultAttributeValues;for(const J in V){const j=V[J];if(j.location>=0){let re=B[J];if(re===void 0&&(J==="instanceMatrix"&&b.instanceMatrix&&(re=b.instanceMatrix),J==="instanceColor"&&b.instanceColor&&(re=b.instanceColor)),re!==void 0){const le=re.normalized,Re=re.itemSize,Ne=e.get(re);if(Ne===void 0)continue;const Ze=Ne.buffer,it=Ne.type,$=Ne.bytesPerElement,de=it===i.INT||it===i.UNSIGNED_INT||re.gpuType===jl;if(re.isInterleavedBufferAttribute){const ae=re.data,Ue=ae.stride,Fe=re.offset;if(ae.isInstancedInterleavedBuffer){for(let ke=0;ke<j.locationSize;ke++)m(j.location+ke,ae.meshPerAttribute);b.isInstancedMesh!==!0&&z._maxInstanceCount===void 0&&(z._maxInstanceCount=ae.meshPerAttribute*ae.count)}else for(let ke=0;ke<j.locationSize;ke++)g(j.location+ke);i.bindBuffer(i.ARRAY_BUFFER,Ze);for(let ke=0;ke<j.locationSize;ke++)w(j.location+ke,Re/j.locationSize,it,le,Ue*$,(Fe+Re/j.locationSize*ke)*$,de)}else{if(re.isInstancedBufferAttribute){for(let ae=0;ae<j.locationSize;ae++)m(j.location+ae,re.meshPerAttribute);b.isInstancedMesh!==!0&&z._maxInstanceCount===void 0&&(z._maxInstanceCount=re.meshPerAttribute*re.count)}else for(let ae=0;ae<j.locationSize;ae++)g(j.location+ae);i.bindBuffer(i.ARRAY_BUFFER,Ze);for(let ae=0;ae<j.locationSize;ae++)w(j.location+ae,Re/j.locationSize,it,le,Re*$,Re/j.locationSize*ae*$,de)}}else if(G!==void 0){const le=G[J];if(le!==void 0)switch(le.length){case 2:i.vertexAttrib2fv(j.location,le);break;case 3:i.vertexAttrib3fv(j.location,le);break;case 4:i.vertexAttrib4fv(j.location,le);break;default:i.vertexAttrib1fv(j.location,le)}}}}E()}function T(){R();for(const b in n){const A=n[b];for(const U in A){const z=A[U];for(const B in z)h(z[B].object),delete z[B];delete A[U]}delete n[b]}}function L(b){if(n[b.id]===void 0)return;const A=n[b.id];for(const U in A){const z=A[U];for(const B in z)h(z[B].object),delete z[B];delete A[U]}delete n[b.id]}function C(b){for(const A in n){const U=n[A];if(U[b.id]===void 0)continue;const z=U[b.id];for(const B in z)h(z[B].object),delete z[B];delete U[b.id]}}function R(){v(),a=!0,s!==r&&(s=r,c(s.object))}function v(){r.geometry=null,r.program=null,r.wireframe=!1}return{setup:o,reset:R,resetDefaultState:v,dispose:T,releaseStatesOfGeometry:L,releaseStatesOfProgram:C,initAttributes:y,enableAttribute:g,disableUnusedAttributes:E}}function h0(i,e,t){let n;function r(c){n=c}function s(c,h){i.drawArrays(n,c,h),t.update(h,n,1)}function a(c,h,u){u!==0&&(i.drawArraysInstanced(n,c,h,u),t.update(h,n,u))}function o(c,h,u){if(u===0)return;e.get("WEBGL_multi_draw").multiDrawArraysWEBGL(n,c,0,h,0,u);let p=0;for(let _=0;_<u;_++)p+=h[_];t.update(p,n,1)}function l(c,h,u,f){if(u===0)return;const p=e.get("WEBGL_multi_draw");if(p===null)for(let _=0;_<c.length;_++)a(c[_],h[_],f[_]);else{p.multiDrawArraysInstancedWEBGL(n,c,0,h,0,f,0,u);let _=0;for(let y=0;y<u;y++)_+=h[y]*f[y];t.update(_,n,1)}}this.setMode=r,this.render=s,this.renderInstances=a,this.renderMultiDraw=o,this.renderMultiDrawInstances=l}function f0(i,e,t,n){let r;function s(){if(r!==void 0)return r;if(e.has("EXT_texture_filter_anisotropic")===!0){const C=e.get("EXT_texture_filter_anisotropic");r=i.getParameter(C.MAX_TEXTURE_MAX_ANISOTROPY_EXT)}else r=0;return r}function a(C){return!(C!==sn&&n.convert(C)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_FORMAT))}function o(C){const R=C===In&&(e.has("EXT_color_buffer_half_float")||e.has("EXT_color_buffer_float"));return!(C!==Sn&&n.convert(C)!==i.getParameter(i.IMPLEMENTATION_COLOR_READ_TYPE)&&C!==$t&&!R)}function l(C){if(C==="highp"){if(i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.HIGH_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.HIGH_FLOAT).precision>0)return"highp";C="mediump"}return C==="mediump"&&i.getShaderPrecisionFormat(i.VERTEX_SHADER,i.MEDIUM_FLOAT).precision>0&&i.getShaderPrecisionFormat(i.FRAGMENT_SHADER,i.MEDIUM_FLOAT).precision>0?"mediump":"lowp"}let c=t.precision!==void 0?t.precision:"highp";const h=l(c);h!==c&&(console.warn("THREE.WebGLRenderer:",c,"not supported, using",h,"instead."),c=h);const u=t.logarithmicDepthBuffer===!0,f=t.reversedDepthBuffer===!0&&e.has("EXT_clip_control"),p=i.getParameter(i.MAX_TEXTURE_IMAGE_UNITS),_=i.getParameter(i.MAX_VERTEX_TEXTURE_IMAGE_UNITS),y=i.getParameter(i.MAX_TEXTURE_SIZE),g=i.getParameter(i.MAX_CUBE_MAP_TEXTURE_SIZE),m=i.getParameter(i.MAX_VERTEX_ATTRIBS),E=i.getParameter(i.MAX_VERTEX_UNIFORM_VECTORS),w=i.getParameter(i.MAX_VARYING_VECTORS),x=i.getParameter(i.MAX_FRAGMENT_UNIFORM_VECTORS),T=_>0,L=i.getParameter(i.MAX_SAMPLES);return{isWebGL2:!0,getMaxAnisotropy:s,getMaxPrecision:l,textureFormatReadable:a,textureTypeReadable:o,precision:c,logarithmicDepthBuffer:u,reversedDepthBuffer:f,maxTextures:p,maxVertexTextures:_,maxTextureSize:y,maxCubemapSize:g,maxAttributes:m,maxVertexUniforms:E,maxVaryings:w,maxFragmentUniforms:x,vertexTextures:T,maxSamples:L}}function p0(i){const e=this;let t=null,n=0,r=!1,s=!1;const a=new jn,o=new Ve,l={value:null,needsUpdate:!1};this.uniform=l,this.numPlanes=0,this.numIntersection=0,this.init=function(u,f){const p=u.length!==0||f||n!==0||r;return r=f,n=u.length,p},this.beginShadows=function(){s=!0,h(null)},this.endShadows=function(){s=!1},this.setGlobalState=function(u,f){t=h(u,f,0)},this.setState=function(u,f,p){const _=u.clippingPlanes,y=u.clipIntersection,g=u.clipShadows,m=i.get(u);if(!r||_===null||_.length===0||s&&!g)s?h(null):c();else{const E=s?0:n,w=E*4;let x=m.clippingState||null;l.value=x,x=h(_,f,w,p);for(let T=0;T!==w;++T)x[T]=t[T];m.clippingState=x,this.numIntersection=y?this.numPlanes:0,this.numPlanes+=E}};function c(){l.value!==t&&(l.value=t,l.needsUpdate=n>0),e.numPlanes=n,e.numIntersection=0}function h(u,f,p,_){const y=u!==null?u.length:0;let g=null;if(y!==0){if(g=l.value,_!==!0||g===null){const m=p+y*4,E=f.matrixWorldInverse;o.getNormalMatrix(E),(g===null||g.length<m)&&(g=new Float32Array(m));for(let w=0,x=p;w!==y;++w,x+=4)a.copy(u[w]).applyMatrix4(E,o),a.normal.toArray(g,x),g[x+3]=a.constant}l.value=g,l.needsUpdate=!0}return e.numPlanes=y,e.numIntersection=0,g}}function m0(i){let e=new WeakMap;function t(a,o){return o===La?a.mapping=Sr:o===tl&&(a.mapping=wr),a}function n(a){if(a&&a.isTexture){const o=a.mapping;if(o===La||o===tl)if(e.has(a)){const l=e.get(a).texture;return t(l,a.mapping)}else{const l=a.image;if(l&&l.height>0){const c=new Dp(l.height);return c.fromEquirectangularTexture(i,a),e.set(a,c),a.addEventListener("dispose",r),t(c.texture,a.mapping)}else return null}}return a}function r(a){const o=a.target;o.removeEventListener("dispose",r);const l=e.get(o);l!==void 0&&(e.delete(o),l.dispose())}function s(){e=new WeakMap}return{get:n,dispose:s}}const ur=4,Od=[.125,.215,.35,.446,.526,.582],Pi=20,No=new uc,Bd=new Ee;let Uo=null,Fo=0,Oo=0,Bo=!1;const Ri=(1+Math.sqrt(5))/2,ar=1/Ri,zd=[new P(-Ri,ar,0),new P(Ri,ar,0),new P(-ar,0,Ri),new P(ar,0,Ri),new P(0,Ri,-ar),new P(0,Ri,ar),new P(-1,1,-1),new P(1,1,-1),new P(-1,1,1),new P(1,1,1)],g0=new P;class Ba{constructor(e){this._renderer=e,this._pingPongRenderTarget=null,this._lodMax=0,this._cubeSize=0,this._lodPlanes=[],this._sizeLods=[],this._sigmas=[],this._blurMaterial=null,this._cubemapMaterial=null,this._equirectMaterial=null,this._compileMaterial(this._blurMaterial)}fromScene(e,t=0,n=.1,r=100,s={}){const{size:a=256,position:o=g0}=s;Uo=this._renderer.getRenderTarget(),Fo=this._renderer.getActiveCubeFace(),Oo=this._renderer.getActiveMipmapLevel(),Bo=this._renderer.xr.enabled,this._renderer.xr.enabled=!1,this._setSize(a);const l=this._allocateTargets();return l.depthBuffer=!0,this._sceneToCubeUV(e,n,r,l,o),t>0&&this._blur(l,0,0,t),this._applyPMREM(l),this._cleanup(l),l}fromEquirectangular(e,t=null){return this._fromTexture(e,t)}fromCubemap(e,t=null){return this._fromTexture(e,t)}compileCubemapShader(){this._cubemapMaterial===null&&(this._cubemapMaterial=Gd(),this._compileMaterial(this._cubemapMaterial))}compileEquirectangularShader(){this._equirectMaterial===null&&(this._equirectMaterial=Hd(),this._compileMaterial(this._equirectMaterial))}dispose(){this._dispose(),this._cubemapMaterial!==null&&this._cubemapMaterial.dispose(),this._equirectMaterial!==null&&this._equirectMaterial.dispose()}_setSize(e){this._lodMax=Math.floor(Math.log2(e)),this._cubeSize=Math.pow(2,this._lodMax)}_dispose(){this._blurMaterial!==null&&this._blurMaterial.dispose(),this._pingPongRenderTarget!==null&&this._pingPongRenderTarget.dispose();for(let e=0;e<this._lodPlanes.length;e++)this._lodPlanes[e].dispose()}_cleanup(e){this._renderer.setRenderTarget(Uo,Fo,Oo),this._renderer.xr.enabled=Bo,e.scissorTest=!1,ma(e,0,0,e.width,e.height)}_fromTexture(e,t){e.mapping===Sr||e.mapping===wr?this._setSize(e.image.length===0?16:e.image[0].width||e.image[0].image.width):this._setSize(e.image.width/4),Uo=this._renderer.getRenderTarget(),Fo=this._renderer.getActiveCubeFace(),Oo=this._renderer.getActiveMipmapLevel(),Bo=this._renderer.xr.enabled,this._renderer.xr.enabled=!1;const n=t||this._allocateTargets();return this._textureToCubeUV(e,n),this._applyPMREM(n),this._cleanup(n),n}_allocateTargets(){const e=3*Math.max(this._cubeSize,112),t=4*this._cubeSize,n={magFilter:Tt,minFilter:Tt,generateMipmaps:!1,type:In,format:sn,colorSpace:zt,depthBuffer:!1},r=kd(e,t,n);if(this._pingPongRenderTarget===null||this._pingPongRenderTarget.width!==e||this._pingPongRenderTarget.height!==t){this._pingPongRenderTarget!==null&&this._dispose(),this._pingPongRenderTarget=kd(e,t,n);const{_lodMax:s}=this;({sizeLods:this._sizeLods,lodPlanes:this._lodPlanes,sigmas:this._sigmas}=_0(s)),this._blurMaterial=y0(s,e,t)}return r}_compileMaterial(e){const t=new ut(this._lodPlanes[0],e);this._renderer.compile(t,No)}_sceneToCubeUV(e,t,n,r,s){const l=new Xt(90,1,t,n),c=[1,-1,1,1,1,1],h=[1,1,1,-1,-1,-1],u=this._renderer,f=u.autoClear,p=u.toneMapping;u.getClearColor(Bd),u.toneMapping=pi,u.autoClear=!1,u.state.buffers.depth.getReversed()&&(u.setRenderTarget(r),u.clearDepth(),u.setRenderTarget(null));const y=new Kn({name:"PMREM.Background",side:jt,depthWrite:!1,depthTest:!1}),g=new ut(new yi,y);let m=!1;const E=e.background;E?E.isColor&&(y.color.copy(E),e.background=null,m=!0):(y.color.copy(Bd),m=!0);for(let w=0;w<6;w++){const x=w%3;x===0?(l.up.set(0,c[w],0),l.position.set(s.x,s.y,s.z),l.lookAt(s.x+h[w],s.y,s.z)):x===1?(l.up.set(0,0,c[w]),l.position.set(s.x,s.y,s.z),l.lookAt(s.x,s.y+h[w],s.z)):(l.up.set(0,c[w],0),l.position.set(s.x,s.y,s.z),l.lookAt(s.x,s.y,s.z+h[w]));const T=this._cubeSize;ma(r,x*T,w>2?T:0,T,T),u.setRenderTarget(r),m&&u.render(g,l),u.render(e,l)}g.geometry.dispose(),g.material.dispose(),u.toneMapping=p,u.autoClear=f,e.background=E}_textureToCubeUV(e,t){const n=this._renderer,r=e.mapping===Sr||e.mapping===wr;r?(this._cubemapMaterial===null&&(this._cubemapMaterial=Gd()),this._cubemapMaterial.uniforms.flipEnvMap.value=e.isRenderTargetTexture===!1?-1:1):this._equirectMaterial===null&&(this._equirectMaterial=Hd());const s=r?this._cubemapMaterial:this._equirectMaterial,a=new ut(this._lodPlanes[0],s),o=s.uniforms;o.envMap.value=e;const l=this._cubeSize;ma(t,0,0,3*l,2*l),n.setRenderTarget(t),n.render(a,No)}_applyPMREM(e){const t=this._renderer,n=t.autoClear;t.autoClear=!1;const r=this._lodPlanes.length;for(let s=1;s<r;s++){const a=Math.sqrt(this._sigmas[s]*this._sigmas[s]-this._sigmas[s-1]*this._sigmas[s-1]),o=zd[(r-s-1)%zd.length];this._blur(e,s-1,s,a,o)}t.autoClear=n}_blur(e,t,n,r,s){const a=this._pingPongRenderTarget;this._halfBlur(e,a,t,n,r,"latitudinal",s),this._halfBlur(a,e,n,n,r,"longitudinal",s)}_halfBlur(e,t,n,r,s,a,o){const l=this._renderer,c=this._blurMaterial;a!=="latitudinal"&&a!=="longitudinal"&&console.error("blur direction must be either latitudinal or longitudinal!");const h=3,u=new ut(this._lodPlanes[r],c),f=c.uniforms,p=this._sizeLods[n]-1,_=isFinite(s)?Math.PI/(2*p):2*Math.PI/(2*Pi-1),y=s/_,g=isFinite(s)?1+Math.floor(h*y):Pi;g>Pi&&console.warn(`sigmaRadians, ${s}, is too large and will clip, as it requested ${g} samples when the maximum is set to ${Pi}`);const m=[];let E=0;for(let C=0;C<Pi;++C){const R=C/y,v=Math.exp(-R*R/2);m.push(v),C===0?E+=v:C<g&&(E+=2*v)}for(let C=0;C<m.length;C++)m[C]=m[C]/E;f.envMap.value=e.texture,f.samples.value=g,f.weights.value=m,f.latitudinal.value=a==="latitudinal",o&&(f.poleAxis.value=o);const{_lodMax:w}=this;f.dTheta.value=_,f.mipInt.value=w-n;const x=this._sizeLods[r],T=3*x*(r>w-ur?r-w+ur:0),L=4*(this._cubeSize-x);ma(t,T,L,3*x,2*x),l.setRenderTarget(t),l.render(u,No)}}function _0(i){const e=[],t=[],n=[];let r=i;const s=i-ur+1+Od.length;for(let a=0;a<s;a++){const o=Math.pow(2,r);t.push(o);let l=1/o;a>i-ur?l=Od[a-i+ur-1]:a===0&&(l=0),n.push(l);const c=1/(o-2),h=-c,u=1+c,f=[h,h,u,h,u,u,h,h,u,u,h,u],p=6,_=6,y=3,g=2,m=1,E=new Float32Array(y*_*p),w=new Float32Array(g*_*p),x=new Float32Array(m*_*p);for(let L=0;L<p;L++){const C=L%3*2/3-1,R=L>2?0:-1,v=[C,R,0,C+2/3,R,0,C+2/3,R+1,0,C,R,0,C+2/3,R+1,0,C,R+1,0];E.set(v,y*_*L),w.set(f,g*_*L);const b=[L,L,L,L,L,L];x.set(b,m*_*L)}const T=new yt;T.setAttribute("position",new Ot(E,y)),T.setAttribute("uv",new Ot(w,g)),T.setAttribute("faceIndex",new Ot(x,m)),e.push(T),r>ur&&r--}return{lodPlanes:e,sizeLods:t,sigmas:n}}function kd(i,e,t){const n=new Ni(i,e,t);return n.texture.mapping=Va,n.texture.name="PMREM.cubeUv",n.scissorTest=!0,n}function ma(i,e,t,n,r){i.viewport.set(e,t,n,r),i.scissor.set(e,t,n,r)}function y0(i,e,t){const n=new Float32Array(Pi),r=new P(0,1,0);return new ti({name:"SphericalGaussianBlur",defines:{n:Pi,CUBEUV_TEXEL_WIDTH:1/e,CUBEUV_TEXEL_HEIGHT:1/t,CUBEUV_MAX_MIP:`${i}.0`},uniforms:{envMap:{value:null},samples:{value:1},weights:{value:n},latitudinal:{value:!1},dTheta:{value:0},mipInt:{value:0},poleAxis:{value:r}},vertexShader:pc(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;
			uniform int samples;
			uniform float weights[ n ];
			uniform bool latitudinal;
			uniform float dTheta;
			uniform float mipInt;
			uniform vec3 poleAxis;

			#define ENVMAP_TYPE_CUBE_UV
			#include <cube_uv_reflection_fragment>

			vec3 getSample( float theta, vec3 axis ) {

				float cosTheta = cos( theta );
				// Rodrigues' axis-angle rotation
				vec3 sampleDirection = vOutputDirection * cosTheta
					+ cross( axis, vOutputDirection ) * sin( theta )
					+ axis * dot( axis, vOutputDirection ) * ( 1.0 - cosTheta );

				return bilinearCubeUV( envMap, sampleDirection, mipInt );

			}

			void main() {

				vec3 axis = latitudinal ? poleAxis : cross( poleAxis, vOutputDirection );

				if ( all( equal( axis, vec3( 0.0 ) ) ) ) {

					axis = vec3( vOutputDirection.z, 0.0, - vOutputDirection.x );

				}

				axis = normalize( axis );

				gl_FragColor = vec4( 0.0, 0.0, 0.0, 1.0 );
				gl_FragColor.rgb += weights[ 0 ] * getSample( 0.0, axis );

				for ( int i = 1; i < n; i++ ) {

					if ( i >= samples ) {

						break;

					}

					float theta = dTheta * float( i );
					gl_FragColor.rgb += weights[ i ] * getSample( -1.0 * theta, axis );
					gl_FragColor.rgb += weights[ i ] * getSample( theta, axis );

				}

			}
		`,blending:fi,depthTest:!1,depthWrite:!1})}function Hd(){return new ti({name:"EquirectangularToCubeUV",uniforms:{envMap:{value:null}},vertexShader:pc(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			varying vec3 vOutputDirection;

			uniform sampler2D envMap;

			#include <common>

			void main() {

				vec3 outputDirection = normalize( vOutputDirection );
				vec2 uv = equirectUv( outputDirection );

				gl_FragColor = vec4( texture2D ( envMap, uv ).rgb, 1.0 );

			}
		`,blending:fi,depthTest:!1,depthWrite:!1})}function Gd(){return new ti({name:"CubemapToCubeUV",uniforms:{envMap:{value:null},flipEnvMap:{value:-1}},vertexShader:pc(),fragmentShader:`

			precision mediump float;
			precision mediump int;

			uniform float flipEnvMap;

			varying vec3 vOutputDirection;

			uniform samplerCube envMap;

			void main() {

				gl_FragColor = textureCube( envMap, vec3( flipEnvMap * vOutputDirection.x, vOutputDirection.yz ) );

			}
		`,blending:fi,depthTest:!1,depthWrite:!1})}function pc(){return`

		precision mediump float;
		precision mediump int;

		attribute float faceIndex;

		varying vec3 vOutputDirection;

		// RH coordinate system; PMREM face-indexing convention
		vec3 getDirection( vec2 uv, float face ) {

			uv = 2.0 * uv - 1.0;

			vec3 direction = vec3( uv, 1.0 );

			if ( face == 0.0 ) {

				direction = direction.zyx; // ( 1, v, u ) pos x

			} else if ( face == 1.0 ) {

				direction = direction.xzy;
				direction.xz *= -1.0; // ( -u, 1, -v ) pos y

			} else if ( face == 2.0 ) {

				direction.x *= -1.0; // ( -u, v, 1 ) pos z

			} else if ( face == 3.0 ) {

				direction = direction.zyx;
				direction.xz *= -1.0; // ( -1, v, -u ) neg x

			} else if ( face == 4.0 ) {

				direction = direction.xzy;
				direction.xy *= -1.0; // ( -u, -1, v ) neg y

			} else if ( face == 5.0 ) {

				direction.z *= -1.0; // ( u, v, -1 ) neg z

			}

			return direction;

		}

		void main() {

			vOutputDirection = getDirection( uv, faceIndex );
			gl_Position = vec4( position, 1.0 );

		}
	`}function x0(i){let e=new WeakMap,t=null;function n(o){if(o&&o.isTexture){const l=o.mapping,c=l===La||l===tl,h=l===Sr||l===wr;if(c||h){let u=e.get(o);const f=u!==void 0?u.texture.pmremVersion:0;if(o.isRenderTargetTexture&&o.pmremVersion!==f)return t===null&&(t=new Ba(i)),u=c?t.fromEquirectangular(o,u):t.fromCubemap(o,u),u.texture.pmremVersion=o.pmremVersion,e.set(o,u),u.texture;if(u!==void 0)return u.texture;{const p=o.image;return c&&p&&p.height>0||h&&p&&r(p)?(t===null&&(t=new Ba(i)),u=c?t.fromEquirectangular(o):t.fromCubemap(o),u.texture.pmremVersion=o.pmremVersion,e.set(o,u),o.addEventListener("dispose",s),u.texture):null}}}return o}function r(o){let l=0;const c=6;for(let h=0;h<c;h++)o[h]!==void 0&&l++;return l===c}function s(o){const l=o.target;l.removeEventListener("dispose",s);const c=e.get(l);c!==void 0&&(e.delete(l),c.dispose())}function a(){e=new WeakMap,t!==null&&(t.dispose(),t=null)}return{get:n,dispose:a}}function v0(i){const e={};function t(n){if(e[n]!==void 0)return e[n];let r;switch(n){case"WEBGL_depth_texture":r=i.getExtension("WEBGL_depth_texture")||i.getExtension("MOZ_WEBGL_depth_texture")||i.getExtension("WEBKIT_WEBGL_depth_texture");break;case"EXT_texture_filter_anisotropic":r=i.getExtension("EXT_texture_filter_anisotropic")||i.getExtension("MOZ_EXT_texture_filter_anisotropic")||i.getExtension("WEBKIT_EXT_texture_filter_anisotropic");break;case"WEBGL_compressed_texture_s3tc":r=i.getExtension("WEBGL_compressed_texture_s3tc")||i.getExtension("MOZ_WEBGL_compressed_texture_s3tc")||i.getExtension("WEBKIT_WEBGL_compressed_texture_s3tc");break;case"WEBGL_compressed_texture_pvrtc":r=i.getExtension("WEBGL_compressed_texture_pvrtc")||i.getExtension("WEBKIT_WEBGL_compressed_texture_pvrtc");break;default:r=i.getExtension(n)}return e[n]=r,r}return{has:function(n){return t(n)!==null},init:function(){t("EXT_color_buffer_float"),t("WEBGL_clip_cull_distance"),t("OES_texture_float_linear"),t("EXT_color_buffer_half_float"),t("WEBGL_multisampled_render_to_texture"),t("WEBGL_render_shared_exponent")},get:function(n){const r=t(n);return r===null&&_r("THREE.WebGLRenderer: "+n+" extension not supported."),r}}}function M0(i,e,t,n){const r={},s=new WeakMap;function a(u){const f=u.target;f.index!==null&&e.remove(f.index);for(const _ in f.attributes)e.remove(f.attributes[_]);f.removeEventListener("dispose",a),delete r[f.id];const p=s.get(f);p&&(e.remove(p),s.delete(f)),n.releaseStatesOfGeometry(f),f.isInstancedBufferGeometry===!0&&delete f._maxInstanceCount,t.memory.geometries--}function o(u,f){return r[f.id]===!0||(f.addEventListener("dispose",a),r[f.id]=!0,t.memory.geometries++),f}function l(u){const f=u.attributes;for(const p in f)e.update(f[p],i.ARRAY_BUFFER)}function c(u){const f=[],p=u.index,_=u.attributes.position;let y=0;if(p!==null){const E=p.array;y=p.version;for(let w=0,x=E.length;w<x;w+=3){const T=E[w+0],L=E[w+1],C=E[w+2];f.push(T,L,L,C,C,T)}}else if(_!==void 0){const E=_.array;y=_.version;for(let w=0,x=E.length/3-1;w<x;w+=3){const T=w+0,L=w+1,C=w+2;f.push(T,L,L,C,C,T)}}else return;const g=new(zu(f)?Vu:Gu)(f,1);g.version=y;const m=s.get(u);m&&e.remove(m),s.set(u,g)}function h(u){const f=s.get(u);if(f){const p=u.index;p!==null&&f.version<p.version&&c(u)}else c(u);return s.get(u)}return{get:o,update:l,getWireframeAttribute:h}}function b0(i,e,t){let n;function r(f){n=f}let s,a;function o(f){s=f.type,a=f.bytesPerElement}function l(f,p){i.drawElements(n,p,s,f*a),t.update(p,n,1)}function c(f,p,_){_!==0&&(i.drawElementsInstanced(n,p,s,f*a,_),t.update(p,n,_))}function h(f,p,_){if(_===0)return;e.get("WEBGL_multi_draw").multiDrawElementsWEBGL(n,p,0,s,f,0,_);let g=0;for(let m=0;m<_;m++)g+=p[m];t.update(g,n,1)}function u(f,p,_,y){if(_===0)return;const g=e.get("WEBGL_multi_draw");if(g===null)for(let m=0;m<f.length;m++)c(f[m]/a,p[m],y[m]);else{g.multiDrawElementsInstancedWEBGL(n,p,0,s,f,0,y,0,_);let m=0;for(let E=0;E<_;E++)m+=p[E]*y[E];t.update(m,n,1)}}this.setMode=r,this.setIndex=o,this.render=l,this.renderInstances=c,this.renderMultiDraw=h,this.renderMultiDrawInstances=u}function S0(i){const e={geometries:0,textures:0},t={frame:0,calls:0,triangles:0,points:0,lines:0};function n(s,a,o){switch(t.calls++,a){case i.TRIANGLES:t.triangles+=o*(s/3);break;case i.LINES:t.lines+=o*(s/2);break;case i.LINE_STRIP:t.lines+=o*(s-1);break;case i.LINE_LOOP:t.lines+=o*s;break;case i.POINTS:t.points+=o*s;break;default:console.error("THREE.WebGLInfo: Unknown draw mode:",a);break}}function r(){t.calls=0,t.triangles=0,t.points=0,t.lines=0}return{memory:e,render:t,programs:null,autoReset:!0,reset:r,update:n}}function w0(i,e,t){const n=new WeakMap,r=new Ye;function s(a,o,l){const c=a.morphTargetInfluences,h=o.morphAttributes.position||o.morphAttributes.normal||o.morphAttributes.color,u=h!==void 0?h.length:0;let f=n.get(o);if(f===void 0||f.count!==u){let b=function(){R.dispose(),n.delete(o),o.removeEventListener("dispose",b)};var p=b;f!==void 0&&f.texture.dispose();const _=o.morphAttributes.position!==void 0,y=o.morphAttributes.normal!==void 0,g=o.morphAttributes.color!==void 0,m=o.morphAttributes.position||[],E=o.morphAttributes.normal||[],w=o.morphAttributes.color||[];let x=0;_===!0&&(x=1),y===!0&&(x=2),g===!0&&(x=3);let T=o.attributes.position.count*x,L=1;T>e.maxTextureSize&&(L=Math.ceil(T/e.maxTextureSize),T=e.maxTextureSize);const C=new Float32Array(T*L*4*u),R=new ku(C,T,L,u);R.type=$t,R.needsUpdate=!0;const v=x*4;for(let A=0;A<u;A++){const U=m[A],z=E[A],B=w[A],V=T*L*4*A;for(let G=0;G<U.count;G++){const J=G*v;_===!0&&(r.fromBufferAttribute(U,G),C[V+J+0]=r.x,C[V+J+1]=r.y,C[V+J+2]=r.z,C[V+J+3]=0),y===!0&&(r.fromBufferAttribute(z,G),C[V+J+4]=r.x,C[V+J+5]=r.y,C[V+J+6]=r.z,C[V+J+7]=0),g===!0&&(r.fromBufferAttribute(B,G),C[V+J+8]=r.x,C[V+J+9]=r.y,C[V+J+10]=r.z,C[V+J+11]=B.itemSize===4?r.w:1)}}f={count:u,texture:R,size:new xe(T,L)},n.set(o,f),o.addEventListener("dispose",b)}if(a.isInstancedMesh===!0&&a.morphTexture!==null)l.getUniforms().setValue(i,"morphTexture",a.morphTexture,t);else{let _=0;for(let g=0;g<c.length;g++)_+=c[g];const y=o.morphTargetsRelative?1:1-_;l.getUniforms().setValue(i,"morphTargetBaseInfluence",y),l.getUniforms().setValue(i,"morphTargetInfluences",c)}l.getUniforms().setValue(i,"morphTargetsTexture",f.texture,t),l.getUniforms().setValue(i,"morphTargetsTextureSize",f.size)}return{update:s}}function E0(i,e,t,n){let r=new WeakMap;function s(l){const c=n.render.frame,h=l.geometry,u=e.get(l,h);if(r.get(u)!==c&&(e.update(u),r.set(u,c)),l.isInstancedMesh&&(l.hasEventListener("dispose",o)===!1&&l.addEventListener("dispose",o),r.get(l)!==c&&(t.update(l.instanceMatrix,i.ARRAY_BUFFER),l.instanceColor!==null&&t.update(l.instanceColor,i.ARRAY_BUFFER),r.set(l,c))),l.isSkinnedMesh){const f=l.skeleton;r.get(f)!==c&&(f.update(),r.set(f,c))}return u}function a(){r=new WeakMap}function o(l){const c=l.target;c.removeEventListener("dispose",o),t.remove(c.instanceMatrix),c.instanceColor!==null&&t.remove(c.instanceColor)}return{update:s,dispose:a}}const lh=new Ct,Vd=new Qu(1,1),ch=new ku,dh=new fp,uh=new ju,Wd=[],Xd=[],jd=new Float32Array(16),qd=new Float32Array(9),Yd=new Float32Array(4);function zr(i,e,t){const n=i[0];if(n<=0||n>0)return i;const r=e*t;let s=Wd[r];if(s===void 0&&(s=new Float32Array(r),Wd[r]=s),e!==0){n.toArray(s,0);for(let a=1,o=0;a!==e;++a)o+=t,i[a].toArray(s,o)}return s}function It(i,e){if(i.length!==e.length)return!1;for(let t=0,n=i.length;t<n;t++)if(i[t]!==e[t])return!1;return!0}function Lt(i,e){for(let t=0,n=e.length;t<n;t++)i[t]=e[t]}function qa(i,e){let t=Xd[e];t===void 0&&(t=new Int32Array(e),Xd[e]=t);for(let n=0;n!==e;++n)t[n]=i.allocateTextureUnit();return t}function T0(i,e){const t=this.cache;t[0]!==e&&(i.uniform1f(this.addr,e),t[0]=e)}function A0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2f(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(It(t,e))return;i.uniform2fv(this.addr,e),Lt(t,e)}}function R0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3f(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else if(e.r!==void 0)(t[0]!==e.r||t[1]!==e.g||t[2]!==e.b)&&(i.uniform3f(this.addr,e.r,e.g,e.b),t[0]=e.r,t[1]=e.g,t[2]=e.b);else{if(It(t,e))return;i.uniform3fv(this.addr,e),Lt(t,e)}}function C0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4f(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(It(t,e))return;i.uniform4fv(this.addr,e),Lt(t,e)}}function P0(i,e){const t=this.cache,n=e.elements;if(n===void 0){if(It(t,e))return;i.uniformMatrix2fv(this.addr,!1,e),Lt(t,e)}else{if(It(t,n))return;Yd.set(n),i.uniformMatrix2fv(this.addr,!1,Yd),Lt(t,n)}}function I0(i,e){const t=this.cache,n=e.elements;if(n===void 0){if(It(t,e))return;i.uniformMatrix3fv(this.addr,!1,e),Lt(t,e)}else{if(It(t,n))return;qd.set(n),i.uniformMatrix3fv(this.addr,!1,qd),Lt(t,n)}}function L0(i,e){const t=this.cache,n=e.elements;if(n===void 0){if(It(t,e))return;i.uniformMatrix4fv(this.addr,!1,e),Lt(t,e)}else{if(It(t,n))return;jd.set(n),i.uniformMatrix4fv(this.addr,!1,jd),Lt(t,n)}}function D0(i,e){const t=this.cache;t[0]!==e&&(i.uniform1i(this.addr,e),t[0]=e)}function N0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2i(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(It(t,e))return;i.uniform2iv(this.addr,e),Lt(t,e)}}function U0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3i(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else{if(It(t,e))return;i.uniform3iv(this.addr,e),Lt(t,e)}}function F0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4i(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(It(t,e))return;i.uniform4iv(this.addr,e),Lt(t,e)}}function O0(i,e){const t=this.cache;t[0]!==e&&(i.uniform1ui(this.addr,e),t[0]=e)}function B0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y)&&(i.uniform2ui(this.addr,e.x,e.y),t[0]=e.x,t[1]=e.y);else{if(It(t,e))return;i.uniform2uiv(this.addr,e),Lt(t,e)}}function z0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z)&&(i.uniform3ui(this.addr,e.x,e.y,e.z),t[0]=e.x,t[1]=e.y,t[2]=e.z);else{if(It(t,e))return;i.uniform3uiv(this.addr,e),Lt(t,e)}}function k0(i,e){const t=this.cache;if(e.x!==void 0)(t[0]!==e.x||t[1]!==e.y||t[2]!==e.z||t[3]!==e.w)&&(i.uniform4ui(this.addr,e.x,e.y,e.z,e.w),t[0]=e.x,t[1]=e.y,t[2]=e.z,t[3]=e.w);else{if(It(t,e))return;i.uniform4uiv(this.addr,e),Lt(t,e)}}function H0(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r);let s;this.type===i.SAMPLER_2D_SHADOW?(Vd.compareFunction=Bu,s=Vd):s=lh,t.setTexture2D(e||s,r)}function G0(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r),t.setTexture3D(e||dh,r)}function V0(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r),t.setTextureCube(e||uh,r)}function W0(i,e,t){const n=this.cache,r=t.allocateTextureUnit();n[0]!==r&&(i.uniform1i(this.addr,r),n[0]=r),t.setTexture2DArray(e||ch,r)}function X0(i){switch(i){case 5126:return T0;case 35664:return A0;case 35665:return R0;case 35666:return C0;case 35674:return P0;case 35675:return I0;case 35676:return L0;case 5124:case 35670:return D0;case 35667:case 35671:return N0;case 35668:case 35672:return U0;case 35669:case 35673:return F0;case 5125:return O0;case 36294:return B0;case 36295:return z0;case 36296:return k0;case 35678:case 36198:case 36298:case 36306:case 35682:return H0;case 35679:case 36299:case 36307:return G0;case 35680:case 36300:case 36308:case 36293:return V0;case 36289:case 36303:case 36311:case 36292:return W0}}function j0(i,e){i.uniform1fv(this.addr,e)}function q0(i,e){const t=zr(e,this.size,2);i.uniform2fv(this.addr,t)}function Y0(i,e){const t=zr(e,this.size,3);i.uniform3fv(this.addr,t)}function K0(i,e){const t=zr(e,this.size,4);i.uniform4fv(this.addr,t)}function $0(i,e){const t=zr(e,this.size,4);i.uniformMatrix2fv(this.addr,!1,t)}function Z0(i,e){const t=zr(e,this.size,9);i.uniformMatrix3fv(this.addr,!1,t)}function J0(i,e){const t=zr(e,this.size,16);i.uniformMatrix4fv(this.addr,!1,t)}function Q0(i,e){i.uniform1iv(this.addr,e)}function ey(i,e){i.uniform2iv(this.addr,e)}function ty(i,e){i.uniform3iv(this.addr,e)}function ny(i,e){i.uniform4iv(this.addr,e)}function iy(i,e){i.uniform1uiv(this.addr,e)}function ry(i,e){i.uniform2uiv(this.addr,e)}function sy(i,e){i.uniform3uiv(this.addr,e)}function ay(i,e){i.uniform4uiv(this.addr,e)}function oy(i,e,t){const n=this.cache,r=e.length,s=qa(t,r);It(n,s)||(i.uniform1iv(this.addr,s),Lt(n,s));for(let a=0;a!==r;++a)t.setTexture2D(e[a]||lh,s[a])}function ly(i,e,t){const n=this.cache,r=e.length,s=qa(t,r);It(n,s)||(i.uniform1iv(this.addr,s),Lt(n,s));for(let a=0;a!==r;++a)t.setTexture3D(e[a]||dh,s[a])}function cy(i,e,t){const n=this.cache,r=e.length,s=qa(t,r);It(n,s)||(i.uniform1iv(this.addr,s),Lt(n,s));for(let a=0;a!==r;++a)t.setTextureCube(e[a]||uh,s[a])}function dy(i,e,t){const n=this.cache,r=e.length,s=qa(t,r);It(n,s)||(i.uniform1iv(this.addr,s),Lt(n,s));for(let a=0;a!==r;++a)t.setTexture2DArray(e[a]||ch,s[a])}function uy(i){switch(i){case 5126:return j0;case 35664:return q0;case 35665:return Y0;case 35666:return K0;case 35674:return $0;case 35675:return Z0;case 35676:return J0;case 5124:case 35670:return Q0;case 35667:case 35671:return ey;case 35668:case 35672:return ty;case 35669:case 35673:return ny;case 5125:return iy;case 36294:return ry;case 36295:return sy;case 36296:return ay;case 35678:case 36198:case 36298:case 36306:case 35682:return oy;case 35679:case 36299:case 36307:return ly;case 35680:case 36300:case 36308:case 36293:return cy;case 36289:case 36303:case 36311:case 36292:return dy}}class hy{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.setValue=X0(t.type)}}class fy{constructor(e,t,n){this.id=e,this.addr=n,this.cache=[],this.type=t.type,this.size=t.size,this.setValue=uy(t.type)}}class py{constructor(e){this.id=e,this.seq=[],this.map={}}setValue(e,t,n){const r=this.seq;for(let s=0,a=r.length;s!==a;++s){const o=r[s];o.setValue(e,t[o.id],n)}}}const zo=/(\w+)(\])?(\[|\.)?/g;function Kd(i,e){i.seq.push(e),i.map[e.id]=e}function my(i,e,t){const n=i.name,r=n.length;for(zo.lastIndex=0;;){const s=zo.exec(n),a=zo.lastIndex;let o=s[1];const l=s[2]==="]",c=s[3];if(l&&(o=o|0),c===void 0||c==="["&&a+2===r){Kd(t,c===void 0?new hy(o,i,e):new fy(o,i,e));break}else{let u=t.map[o];u===void 0&&(u=new py(o),Kd(t,u)),t=u}}}class Ea{constructor(e,t){this.seq=[],this.map={};const n=e.getProgramParameter(t,e.ACTIVE_UNIFORMS);for(let r=0;r<n;++r){const s=e.getActiveUniform(t,r),a=e.getUniformLocation(t,s.name);my(s,a,this)}}setValue(e,t,n,r){const s=this.map[t];s!==void 0&&s.setValue(e,n,r)}setOptional(e,t,n){const r=t[n];r!==void 0&&this.setValue(e,n,r)}static upload(e,t,n,r){for(let s=0,a=t.length;s!==a;++s){const o=t[s],l=n[o.id];l.needsUpdate!==!1&&o.setValue(e,l.value,r)}}static seqWithValue(e,t){const n=[];for(let r=0,s=e.length;r!==s;++r){const a=e[r];a.id in t&&n.push(a)}return n}}function $d(i,e,t){const n=i.createShader(e);return i.shaderSource(n,t),i.compileShader(n),n}const gy=37297;let _y=0;function yy(i,e){const t=i.split(`
`),n=[],r=Math.max(e-6,0),s=Math.min(e+6,t.length);for(let a=r;a<s;a++){const o=a+1;n.push(`${o===e?">":" "} ${o}: ${t[a]}`)}return n.join(`
`)}const Zd=new Ve;function xy(i){Je._getMatrix(Zd,Je.workingColorSpace,i);const e=`mat3( ${Zd.elements.map(t=>t.toFixed(4))} )`;switch(Je.getTransfer(i)){case Na:return[e,"LinearTransferOETF"];case lt:return[e,"sRGBTransferOETF"];default:return console.warn("THREE.WebGLProgram: Unsupported color space: ",i),[e,"LinearTransferOETF"]}}function Jd(i,e,t){const n=i.getShaderParameter(e,i.COMPILE_STATUS),s=(i.getShaderInfoLog(e)||"").trim();if(n&&s==="")return"";const a=/ERROR: 0:(\d+)/.exec(s);if(a){const o=parseInt(a[1]);return t.toUpperCase()+`

`+s+`

`+yy(i.getShaderSource(e),o)}else return s}function vy(i,e){const t=xy(e);return[`vec4 ${i}( vec4 value ) {`,`	return ${t[1]}( vec4( value.rgb * ${t[0]}, value.a ) );`,"}"].join(`
`)}function My(i,e){let t;switch(e){case Ef:t="Linear";break;case Tf:t="Reinhard";break;case Af:t="Cineon";break;case Au:t="ACESFilmic";break;case Cf:t="AgX";break;case Pf:t="Neutral";break;case Rf:t="Custom";break;default:console.warn("THREE.WebGLProgram: Unsupported toneMapping:",e),t="Linear"}return"vec3 "+i+"( vec3 color ) { return "+t+"ToneMapping( color ); }"}const ga=new P;function by(){Je.getLuminanceCoefficients(ga);const i=ga.x.toFixed(4),e=ga.y.toFixed(4),t=ga.z.toFixed(4);return["float luminance( const in vec3 rgb ) {",`	const vec3 weights = vec3( ${i}, ${e}, ${t} );`,"	return dot( weights, rgb );","}"].join(`
`)}function Sy(i){return[i.extensionClipCullDistance?"#extension GL_ANGLE_clip_cull_distance : require":"",i.extensionMultiDraw?"#extension GL_ANGLE_multi_draw : require":""].filter(is).join(`
`)}function wy(i){const e=[];for(const t in i){const n=i[t];n!==!1&&e.push("#define "+t+" "+n)}return e.join(`
`)}function Ey(i,e){const t={},n=i.getProgramParameter(e,i.ACTIVE_ATTRIBUTES);for(let r=0;r<n;r++){const s=i.getActiveAttrib(e,r),a=s.name;let o=1;s.type===i.FLOAT_MAT2&&(o=2),s.type===i.FLOAT_MAT3&&(o=3),s.type===i.FLOAT_MAT4&&(o=4),t[a]={type:s.type,location:i.getAttribLocation(e,a),locationSize:o}}return t}function is(i){return i!==""}function Qd(i,e){const t=e.numSpotLightShadows+e.numSpotLightMaps-e.numSpotLightShadowsWithMaps;return i.replace(/NUM_DIR_LIGHTS/g,e.numDirLights).replace(/NUM_SPOT_LIGHTS/g,e.numSpotLights).replace(/NUM_SPOT_LIGHT_MAPS/g,e.numSpotLightMaps).replace(/NUM_SPOT_LIGHT_COORDS/g,t).replace(/NUM_RECT_AREA_LIGHTS/g,e.numRectAreaLights).replace(/NUM_POINT_LIGHTS/g,e.numPointLights).replace(/NUM_HEMI_LIGHTS/g,e.numHemiLights).replace(/NUM_DIR_LIGHT_SHADOWS/g,e.numDirLightShadows).replace(/NUM_SPOT_LIGHT_SHADOWS_WITH_MAPS/g,e.numSpotLightShadowsWithMaps).replace(/NUM_SPOT_LIGHT_SHADOWS/g,e.numSpotLightShadows).replace(/NUM_POINT_LIGHT_SHADOWS/g,e.numPointLightShadows)}function eu(i,e){return i.replace(/NUM_CLIPPING_PLANES/g,e.numClippingPlanes).replace(/UNION_CLIPPING_PLANES/g,e.numClippingPlanes-e.numClipIntersection)}const Ty=/^[ \t]*#include +<([\w\d./]+)>/gm;function Dl(i){return i.replace(Ty,Ry)}const Ay=new Map;function Ry(i,e){let t=We[e];if(t===void 0){const n=Ay.get(e);if(n!==void 0)t=We[n],console.warn('THREE.WebGLRenderer: Shader chunk "%s" has been deprecated. Use "%s" instead.',e,n);else throw new Error("Can not resolve #include <"+e+">")}return Dl(t)}const Cy=/#pragma unroll_loop_start\s+for\s*\(\s*int\s+i\s*=\s*(\d+)\s*;\s*i\s*<\s*(\d+)\s*;\s*i\s*\+\+\s*\)\s*{([\s\S]+?)}\s+#pragma unroll_loop_end/g;function tu(i){return i.replace(Cy,Py)}function Py(i,e,t,n){let r="";for(let s=parseInt(e);s<parseInt(t);s++)r+=n.replace(/\[\s*i\s*\]/g,"[ "+s+" ]").replace(/UNROLLED_LOOP_INDEX/g,s);return r}function nu(i){let e=`precision ${i.precision} float;
	precision ${i.precision} int;
	precision ${i.precision} sampler2D;
	precision ${i.precision} samplerCube;
	precision ${i.precision} sampler3D;
	precision ${i.precision} sampler2DArray;
	precision ${i.precision} sampler2DShadow;
	precision ${i.precision} samplerCubeShadow;
	precision ${i.precision} sampler2DArrayShadow;
	precision ${i.precision} isampler2D;
	precision ${i.precision} isampler3D;
	precision ${i.precision} isamplerCube;
	precision ${i.precision} isampler2DArray;
	precision ${i.precision} usampler2D;
	precision ${i.precision} usampler3D;
	precision ${i.precision} usamplerCube;
	precision ${i.precision} usampler2DArray;
	`;return i.precision==="highp"?e+=`
#define HIGH_PRECISION`:i.precision==="mediump"?e+=`
#define MEDIUM_PRECISION`:i.precision==="lowp"&&(e+=`
#define LOW_PRECISION`),e}function Iy(i){let e="SHADOWMAP_TYPE_BASIC";return i.shadowMapType===Eu?e="SHADOWMAP_TYPE_PCF":i.shadowMapType===Tu?e="SHADOWMAP_TYPE_PCF_SOFT":i.shadowMapType===Wn&&(e="SHADOWMAP_TYPE_VSM"),e}function Ly(i){let e="ENVMAP_TYPE_CUBE";if(i.envMap)switch(i.envMapMode){case Sr:case wr:e="ENVMAP_TYPE_CUBE";break;case Va:e="ENVMAP_TYPE_CUBE_UV";break}return e}function Dy(i){let e="ENVMAP_MODE_REFLECTION";return i.envMap&&i.envMapMode===wr&&(e="ENVMAP_MODE_REFRACTION"),e}function Ny(i){let e="ENVMAP_BLENDING_NONE";if(i.envMap)switch(i.combine){case Xl:e="ENVMAP_BLENDING_MULTIPLY";break;case Sf:e="ENVMAP_BLENDING_MIX";break;case wf:e="ENVMAP_BLENDING_ADD";break}return e}function Uy(i){const e=i.envMapCubeUVHeight;if(e===null)return null;const t=Math.log2(e)-2,n=1/e;return{texelWidth:1/(3*Math.max(Math.pow(2,t),112)),texelHeight:n,maxMip:t}}function Fy(i,e,t,n){const r=i.getContext(),s=t.defines;let a=t.vertexShader,o=t.fragmentShader;const l=Iy(t),c=Ly(t),h=Dy(t),u=Ny(t),f=Uy(t),p=Sy(t),_=wy(s),y=r.createProgram();let g,m,E=t.glslVersion?"#version "+t.glslVersion+`
`:"";t.isRawShaderMaterial?(g=["#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_].filter(is).join(`
`),g.length>0&&(g+=`
`),m=["#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_].filter(is).join(`
`),m.length>0&&(m+=`
`)):(g=[nu(t),"#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_,t.extensionClipCullDistance?"#define USE_CLIP_DISTANCE":"",t.batching?"#define USE_BATCHING":"",t.batchingColor?"#define USE_BATCHING_COLOR":"",t.instancing?"#define USE_INSTANCING":"",t.instancingColor?"#define USE_INSTANCING_COLOR":"",t.instancingMorph?"#define USE_INSTANCING_MORPH":"",t.useFog&&t.fog?"#define USE_FOG":"",t.useFog&&t.fogExp2?"#define FOG_EXP2":"",t.map?"#define USE_MAP":"",t.envMap?"#define USE_ENVMAP":"",t.envMap?"#define "+h:"",t.lightMap?"#define USE_LIGHTMAP":"",t.aoMap?"#define USE_AOMAP":"",t.bumpMap?"#define USE_BUMPMAP":"",t.normalMap?"#define USE_NORMALMAP":"",t.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",t.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",t.displacementMap?"#define USE_DISPLACEMENTMAP":"",t.emissiveMap?"#define USE_EMISSIVEMAP":"",t.anisotropy?"#define USE_ANISOTROPY":"",t.anisotropyMap?"#define USE_ANISOTROPYMAP":"",t.clearcoatMap?"#define USE_CLEARCOATMAP":"",t.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",t.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",t.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",t.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",t.specularMap?"#define USE_SPECULARMAP":"",t.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",t.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",t.roughnessMap?"#define USE_ROUGHNESSMAP":"",t.metalnessMap?"#define USE_METALNESSMAP":"",t.alphaMap?"#define USE_ALPHAMAP":"",t.alphaHash?"#define USE_ALPHAHASH":"",t.transmission?"#define USE_TRANSMISSION":"",t.transmissionMap?"#define USE_TRANSMISSIONMAP":"",t.thicknessMap?"#define USE_THICKNESSMAP":"",t.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",t.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",t.mapUv?"#define MAP_UV "+t.mapUv:"",t.alphaMapUv?"#define ALPHAMAP_UV "+t.alphaMapUv:"",t.lightMapUv?"#define LIGHTMAP_UV "+t.lightMapUv:"",t.aoMapUv?"#define AOMAP_UV "+t.aoMapUv:"",t.emissiveMapUv?"#define EMISSIVEMAP_UV "+t.emissiveMapUv:"",t.bumpMapUv?"#define BUMPMAP_UV "+t.bumpMapUv:"",t.normalMapUv?"#define NORMALMAP_UV "+t.normalMapUv:"",t.displacementMapUv?"#define DISPLACEMENTMAP_UV "+t.displacementMapUv:"",t.metalnessMapUv?"#define METALNESSMAP_UV "+t.metalnessMapUv:"",t.roughnessMapUv?"#define ROUGHNESSMAP_UV "+t.roughnessMapUv:"",t.anisotropyMapUv?"#define ANISOTROPYMAP_UV "+t.anisotropyMapUv:"",t.clearcoatMapUv?"#define CLEARCOATMAP_UV "+t.clearcoatMapUv:"",t.clearcoatNormalMapUv?"#define CLEARCOAT_NORMALMAP_UV "+t.clearcoatNormalMapUv:"",t.clearcoatRoughnessMapUv?"#define CLEARCOAT_ROUGHNESSMAP_UV "+t.clearcoatRoughnessMapUv:"",t.iridescenceMapUv?"#define IRIDESCENCEMAP_UV "+t.iridescenceMapUv:"",t.iridescenceThicknessMapUv?"#define IRIDESCENCE_THICKNESSMAP_UV "+t.iridescenceThicknessMapUv:"",t.sheenColorMapUv?"#define SHEEN_COLORMAP_UV "+t.sheenColorMapUv:"",t.sheenRoughnessMapUv?"#define SHEEN_ROUGHNESSMAP_UV "+t.sheenRoughnessMapUv:"",t.specularMapUv?"#define SPECULARMAP_UV "+t.specularMapUv:"",t.specularColorMapUv?"#define SPECULAR_COLORMAP_UV "+t.specularColorMapUv:"",t.specularIntensityMapUv?"#define SPECULAR_INTENSITYMAP_UV "+t.specularIntensityMapUv:"",t.transmissionMapUv?"#define TRANSMISSIONMAP_UV "+t.transmissionMapUv:"",t.thicknessMapUv?"#define THICKNESSMAP_UV "+t.thicknessMapUv:"",t.vertexTangents&&t.flatShading===!1?"#define USE_TANGENT":"",t.vertexColors?"#define USE_COLOR":"",t.vertexAlphas?"#define USE_COLOR_ALPHA":"",t.vertexUv1s?"#define USE_UV1":"",t.vertexUv2s?"#define USE_UV2":"",t.vertexUv3s?"#define USE_UV3":"",t.pointsUvs?"#define USE_POINTS_UV":"",t.flatShading?"#define FLAT_SHADED":"",t.skinning?"#define USE_SKINNING":"",t.morphTargets?"#define USE_MORPHTARGETS":"",t.morphNormals&&t.flatShading===!1?"#define USE_MORPHNORMALS":"",t.morphColors?"#define USE_MORPHCOLORS":"",t.morphTargetsCount>0?"#define MORPHTARGETS_TEXTURE_STRIDE "+t.morphTextureStride:"",t.morphTargetsCount>0?"#define MORPHTARGETS_COUNT "+t.morphTargetsCount:"",t.doubleSided?"#define DOUBLE_SIDED":"",t.flipSided?"#define FLIP_SIDED":"",t.shadowMapEnabled?"#define USE_SHADOWMAP":"",t.shadowMapEnabled?"#define "+l:"",t.sizeAttenuation?"#define USE_SIZEATTENUATION":"",t.numLightProbes>0?"#define USE_LIGHT_PROBES":"",t.logarithmicDepthBuffer?"#define USE_LOGDEPTHBUF":"",t.reversedDepthBuffer?"#define USE_REVERSEDEPTHBUF":"","uniform mat4 modelMatrix;","uniform mat4 modelViewMatrix;","uniform mat4 projectionMatrix;","uniform mat4 viewMatrix;","uniform mat3 normalMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;","#ifdef USE_INSTANCING","	attribute mat4 instanceMatrix;","#endif","#ifdef USE_INSTANCING_COLOR","	attribute vec3 instanceColor;","#endif","#ifdef USE_INSTANCING_MORPH","	uniform sampler2D morphTexture;","#endif","attribute vec3 position;","attribute vec3 normal;","attribute vec2 uv;","#ifdef USE_UV1","	attribute vec2 uv1;","#endif","#ifdef USE_UV2","	attribute vec2 uv2;","#endif","#ifdef USE_UV3","	attribute vec2 uv3;","#endif","#ifdef USE_TANGENT","	attribute vec4 tangent;","#endif","#if defined( USE_COLOR_ALPHA )","	attribute vec4 color;","#elif defined( USE_COLOR )","	attribute vec3 color;","#endif","#ifdef USE_SKINNING","	attribute vec4 skinIndex;","	attribute vec4 skinWeight;","#endif",`
`].filter(is).join(`
`),m=[nu(t),"#define SHADER_TYPE "+t.shaderType,"#define SHADER_NAME "+t.shaderName,_,t.useFog&&t.fog?"#define USE_FOG":"",t.useFog&&t.fogExp2?"#define FOG_EXP2":"",t.alphaToCoverage?"#define ALPHA_TO_COVERAGE":"",t.map?"#define USE_MAP":"",t.matcap?"#define USE_MATCAP":"",t.envMap?"#define USE_ENVMAP":"",t.envMap?"#define "+c:"",t.envMap?"#define "+h:"",t.envMap?"#define "+u:"",f?"#define CUBEUV_TEXEL_WIDTH "+f.texelWidth:"",f?"#define CUBEUV_TEXEL_HEIGHT "+f.texelHeight:"",f?"#define CUBEUV_MAX_MIP "+f.maxMip+".0":"",t.lightMap?"#define USE_LIGHTMAP":"",t.aoMap?"#define USE_AOMAP":"",t.bumpMap?"#define USE_BUMPMAP":"",t.normalMap?"#define USE_NORMALMAP":"",t.normalMapObjectSpace?"#define USE_NORMALMAP_OBJECTSPACE":"",t.normalMapTangentSpace?"#define USE_NORMALMAP_TANGENTSPACE":"",t.emissiveMap?"#define USE_EMISSIVEMAP":"",t.anisotropy?"#define USE_ANISOTROPY":"",t.anisotropyMap?"#define USE_ANISOTROPYMAP":"",t.clearcoat?"#define USE_CLEARCOAT":"",t.clearcoatMap?"#define USE_CLEARCOATMAP":"",t.clearcoatRoughnessMap?"#define USE_CLEARCOAT_ROUGHNESSMAP":"",t.clearcoatNormalMap?"#define USE_CLEARCOAT_NORMALMAP":"",t.dispersion?"#define USE_DISPERSION":"",t.iridescence?"#define USE_IRIDESCENCE":"",t.iridescenceMap?"#define USE_IRIDESCENCEMAP":"",t.iridescenceThicknessMap?"#define USE_IRIDESCENCE_THICKNESSMAP":"",t.specularMap?"#define USE_SPECULARMAP":"",t.specularColorMap?"#define USE_SPECULAR_COLORMAP":"",t.specularIntensityMap?"#define USE_SPECULAR_INTENSITYMAP":"",t.roughnessMap?"#define USE_ROUGHNESSMAP":"",t.metalnessMap?"#define USE_METALNESSMAP":"",t.alphaMap?"#define USE_ALPHAMAP":"",t.alphaTest?"#define USE_ALPHATEST":"",t.alphaHash?"#define USE_ALPHAHASH":"",t.sheen?"#define USE_SHEEN":"",t.sheenColorMap?"#define USE_SHEEN_COLORMAP":"",t.sheenRoughnessMap?"#define USE_SHEEN_ROUGHNESSMAP":"",t.transmission?"#define USE_TRANSMISSION":"",t.transmissionMap?"#define USE_TRANSMISSIONMAP":"",t.thicknessMap?"#define USE_THICKNESSMAP":"",t.vertexTangents&&t.flatShading===!1?"#define USE_TANGENT":"",t.vertexColors||t.instancingColor||t.batchingColor?"#define USE_COLOR":"",t.vertexAlphas?"#define USE_COLOR_ALPHA":"",t.vertexUv1s?"#define USE_UV1":"",t.vertexUv2s?"#define USE_UV2":"",t.vertexUv3s?"#define USE_UV3":"",t.pointsUvs?"#define USE_POINTS_UV":"",t.gradientMap?"#define USE_GRADIENTMAP":"",t.flatShading?"#define FLAT_SHADED":"",t.doubleSided?"#define DOUBLE_SIDED":"",t.flipSided?"#define FLIP_SIDED":"",t.shadowMapEnabled?"#define USE_SHADOWMAP":"",t.shadowMapEnabled?"#define "+l:"",t.premultipliedAlpha?"#define PREMULTIPLIED_ALPHA":"",t.numLightProbes>0?"#define USE_LIGHT_PROBES":"",t.decodeVideoTexture?"#define DECODE_VIDEO_TEXTURE":"",t.decodeVideoTextureEmissive?"#define DECODE_VIDEO_TEXTURE_EMISSIVE":"",t.logarithmicDepthBuffer?"#define USE_LOGDEPTHBUF":"",t.reversedDepthBuffer?"#define USE_REVERSEDEPTHBUF":"","uniform mat4 viewMatrix;","uniform vec3 cameraPosition;","uniform bool isOrthographic;",t.toneMapping!==pi?"#define TONE_MAPPING":"",t.toneMapping!==pi?We.tonemapping_pars_fragment:"",t.toneMapping!==pi?My("toneMapping",t.toneMapping):"",t.dithering?"#define DITHERING":"",t.opaque?"#define OPAQUE":"",We.colorspace_pars_fragment,vy("linearToOutputTexel",t.outputColorSpace),by(),t.useDepthPacking?"#define DEPTH_PACKING "+t.depthPacking:"",`
`].filter(is).join(`
`)),a=Dl(a),a=Qd(a,t),a=eu(a,t),o=Dl(o),o=Qd(o,t),o=eu(o,t),a=tu(a),o=tu(o),t.isRawShaderMaterial!==!0&&(E=`#version 300 es
`,g=[p,"#define attribute in","#define varying out","#define texture2D texture"].join(`
`)+`
`+g,m=["#define varying in",t.glslVersion===Yc?"":"layout(location = 0) out highp vec4 pc_fragColor;",t.glslVersion===Yc?"":"#define gl_FragColor pc_fragColor","#define gl_FragDepthEXT gl_FragDepth","#define texture2D texture","#define textureCube texture","#define texture2DProj textureProj","#define texture2DLodEXT textureLod","#define texture2DProjLodEXT textureProjLod","#define textureCubeLodEXT textureLod","#define texture2DGradEXT textureGrad","#define texture2DProjGradEXT textureProjGrad","#define textureCubeGradEXT textureGrad"].join(`
`)+`
`+m);const w=E+g+a,x=E+m+o,T=$d(r,r.VERTEX_SHADER,w),L=$d(r,r.FRAGMENT_SHADER,x);r.attachShader(y,T),r.attachShader(y,L),t.index0AttributeName!==void 0?r.bindAttribLocation(y,0,t.index0AttributeName):t.morphTargets===!0&&r.bindAttribLocation(y,0,"position"),r.linkProgram(y);function C(A){if(i.debug.checkShaderErrors){const U=r.getProgramInfoLog(y)||"",z=r.getShaderInfoLog(T)||"",B=r.getShaderInfoLog(L)||"",V=U.trim(),G=z.trim(),J=B.trim();let j=!0,re=!0;if(r.getProgramParameter(y,r.LINK_STATUS)===!1)if(j=!1,typeof i.debug.onShaderError=="function")i.debug.onShaderError(r,y,T,L);else{const le=Jd(r,T,"vertex"),Re=Jd(r,L,"fragment");console.error("THREE.WebGLProgram: Shader Error "+r.getError()+" - VALIDATE_STATUS "+r.getProgramParameter(y,r.VALIDATE_STATUS)+`

Material Name: `+A.name+`
Material Type: `+A.type+`

Program Info Log: `+V+`
`+le+`
`+Re)}else V!==""?console.warn("THREE.WebGLProgram: Program Info Log:",V):(G===""||J==="")&&(re=!1);re&&(A.diagnostics={runnable:j,programLog:V,vertexShader:{log:G,prefix:g},fragmentShader:{log:J,prefix:m}})}r.deleteShader(T),r.deleteShader(L),R=new Ea(r,y),v=Ey(r,y)}let R;this.getUniforms=function(){return R===void 0&&C(this),R};let v;this.getAttributes=function(){return v===void 0&&C(this),v};let b=t.rendererExtensionParallelShaderCompile===!1;return this.isReady=function(){return b===!1&&(b=r.getProgramParameter(y,gy)),b},this.destroy=function(){n.releaseStatesOfProgram(this),r.deleteProgram(y),this.program=void 0},this.type=t.shaderType,this.name=t.shaderName,this.id=_y++,this.cacheKey=e,this.usedTimes=1,this.program=y,this.vertexShader=T,this.fragmentShader=L,this}let Oy=0;class By{constructor(){this.shaderCache=new Map,this.materialCache=new Map}update(e){const t=e.vertexShader,n=e.fragmentShader,r=this._getShaderStage(t),s=this._getShaderStage(n),a=this._getShaderCacheForMaterial(e);return a.has(r)===!1&&(a.add(r),r.usedTimes++),a.has(s)===!1&&(a.add(s),s.usedTimes++),this}remove(e){const t=this.materialCache.get(e);for(const n of t)n.usedTimes--,n.usedTimes===0&&this.shaderCache.delete(n.code);return this.materialCache.delete(e),this}getVertexShaderID(e){return this._getShaderStage(e.vertexShader).id}getFragmentShaderID(e){return this._getShaderStage(e.fragmentShader).id}dispose(){this.shaderCache.clear(),this.materialCache.clear()}_getShaderCacheForMaterial(e){const t=this.materialCache;let n=t.get(e);return n===void 0&&(n=new Set,t.set(e,n)),n}_getShaderStage(e){const t=this.shaderCache;let n=t.get(e);return n===void 0&&(n=new zy(e),t.set(e,n)),n}}class zy{constructor(e){this.id=Oy++,this.code=e,this.usedTimes=0}}function ky(i,e,t,n,r,s,a){const o=new nc,l=new By,c=new Set,h=[],u=r.logarithmicDepthBuffer,f=r.vertexTextures;let p=r.precision;const _={MeshDepthMaterial:"depth",MeshDistanceMaterial:"distanceRGBA",MeshNormalMaterial:"normal",MeshBasicMaterial:"basic",MeshLambertMaterial:"lambert",MeshPhongMaterial:"phong",MeshToonMaterial:"toon",MeshStandardMaterial:"physical",MeshPhysicalMaterial:"physical",MeshMatcapMaterial:"matcap",LineBasicMaterial:"basic",LineDashedMaterial:"dashed",PointsMaterial:"points",ShadowMaterial:"shadow",SpriteMaterial:"sprite"};function y(v){return c.add(v),v===0?"uv":`uv${v}`}function g(v,b,A,U,z){const B=U.fog,V=z.geometry,G=v.isMeshStandardMaterial?U.environment:null,J=(v.isMeshStandardMaterial?t:e).get(v.envMap||G),j=J&&J.mapping===Va?J.image.height:null,re=_[v.type];v.precision!==null&&(p=r.getMaxPrecision(v.precision),p!==v.precision&&console.warn("THREE.WebGLProgram.getParameters:",v.precision,"not supported, using",p,"instead."));const le=V.morphAttributes.position||V.morphAttributes.normal||V.morphAttributes.color,Re=le!==void 0?le.length:0;let Ne=0;V.morphAttributes.position!==void 0&&(Ne=1),V.morphAttributes.normal!==void 0&&(Ne=2),V.morphAttributes.color!==void 0&&(Ne=3);let Ze,it,$,de;if(re){const rt=Rn[re];Ze=rt.vertexShader,it=rt.fragmentShader}else Ze=v.vertexShader,it=v.fragmentShader,l.update(v),$=l.getVertexShaderID(v),de=l.getFragmentShaderID(v);const ae=i.getRenderTarget(),Ue=i.state.buffers.depth.getReversed(),Fe=z.isInstancedMesh===!0,ke=z.isBatchedMesh===!0,bt=!!v.map,Qe=!!v.matcap,D=!!J,ht=!!v.aoMap,Ie=!!v.lightMap,nt=!!v.bumpMap,Ce=!!v.normalMap,_t=!!v.displacementMap,ge=!!v.emissiveMap,je=!!v.metalnessMap,Dt=!!v.roughnessMap,St=v.anisotropy>0,I=v.clearcoat>0,M=v.dispersion>0,k=v.iridescence>0,K=v.sheen>0,Q=v.transmission>0,Y=St&&!!v.anisotropyMap,Te=I&&!!v.clearcoatMap,se=I&&!!v.clearcoatNormalMap,ve=I&&!!v.clearcoatRoughnessMap,be=k&&!!v.iridescenceMap,ne=k&&!!v.iridescenceThicknessMap,fe=K&&!!v.sheenColorMap,Be=K&&!!v.sheenRoughnessMap,Se=!!v.specularMap,ue=!!v.specularColorMap,Ge=!!v.specularIntensityMap,N=Q&&!!v.transmissionMap,ie=Q&&!!v.thicknessMap,oe=!!v.gradientMap,me=!!v.alphaMap,ee=v.alphaTest>0,Z=!!v.alphaHash,ye=!!v.extensions;let He=pi;v.toneMapped&&(ae===null||ae.isXRRenderTarget===!0)&&(He=i.toneMapping);const ft={shaderID:re,shaderType:v.type,shaderName:v.name,vertexShader:Ze,fragmentShader:it,defines:v.defines,customVertexShaderID:$,customFragmentShaderID:de,isRawShaderMaterial:v.isRawShaderMaterial===!0,glslVersion:v.glslVersion,precision:p,batching:ke,batchingColor:ke&&z._colorsTexture!==null,instancing:Fe,instancingColor:Fe&&z.instanceColor!==null,instancingMorph:Fe&&z.morphTexture!==null,supportsVertexTextures:f,outputColorSpace:ae===null?i.outputColorSpace:ae.isXRRenderTarget===!0?ae.texture.colorSpace:zt,alphaToCoverage:!!v.alphaToCoverage,map:bt,matcap:Qe,envMap:D,envMapMode:D&&J.mapping,envMapCubeUVHeight:j,aoMap:ht,lightMap:Ie,bumpMap:nt,normalMap:Ce,displacementMap:f&&_t,emissiveMap:ge,normalMapObjectSpace:Ce&&v.normalMapType===Ff,normalMapTangentSpace:Ce&&v.normalMapType===Ql,metalnessMap:je,roughnessMap:Dt,anisotropy:St,anisotropyMap:Y,clearcoat:I,clearcoatMap:Te,clearcoatNormalMap:se,clearcoatRoughnessMap:ve,dispersion:M,iridescence:k,iridescenceMap:be,iridescenceThicknessMap:ne,sheen:K,sheenColorMap:fe,sheenRoughnessMap:Be,specularMap:Se,specularColorMap:ue,specularIntensityMap:Ge,transmission:Q,transmissionMap:N,thicknessMap:ie,gradientMap:oe,opaque:v.transparent===!1&&v.blending===mr&&v.alphaToCoverage===!1,alphaMap:me,alphaTest:ee,alphaHash:Z,combine:v.combine,mapUv:bt&&y(v.map.channel),aoMapUv:ht&&y(v.aoMap.channel),lightMapUv:Ie&&y(v.lightMap.channel),bumpMapUv:nt&&y(v.bumpMap.channel),normalMapUv:Ce&&y(v.normalMap.channel),displacementMapUv:_t&&y(v.displacementMap.channel),emissiveMapUv:ge&&y(v.emissiveMap.channel),metalnessMapUv:je&&y(v.metalnessMap.channel),roughnessMapUv:Dt&&y(v.roughnessMap.channel),anisotropyMapUv:Y&&y(v.anisotropyMap.channel),clearcoatMapUv:Te&&y(v.clearcoatMap.channel),clearcoatNormalMapUv:se&&y(v.clearcoatNormalMap.channel),clearcoatRoughnessMapUv:ve&&y(v.clearcoatRoughnessMap.channel),iridescenceMapUv:be&&y(v.iridescenceMap.channel),iridescenceThicknessMapUv:ne&&y(v.iridescenceThicknessMap.channel),sheenColorMapUv:fe&&y(v.sheenColorMap.channel),sheenRoughnessMapUv:Be&&y(v.sheenRoughnessMap.channel),specularMapUv:Se&&y(v.specularMap.channel),specularColorMapUv:ue&&y(v.specularColorMap.channel),specularIntensityMapUv:Ge&&y(v.specularIntensityMap.channel),transmissionMapUv:N&&y(v.transmissionMap.channel),thicknessMapUv:ie&&y(v.thicknessMap.channel),alphaMapUv:me&&y(v.alphaMap.channel),vertexTangents:!!V.attributes.tangent&&(Ce||St),vertexColors:v.vertexColors,vertexAlphas:v.vertexColors===!0&&!!V.attributes.color&&V.attributes.color.itemSize===4,pointsUvs:z.isPoints===!0&&!!V.attributes.uv&&(bt||me),fog:!!B,useFog:v.fog===!0,fogExp2:!!B&&B.isFogExp2,flatShading:v.flatShading===!0&&v.wireframe===!1,sizeAttenuation:v.sizeAttenuation===!0,logarithmicDepthBuffer:u,reversedDepthBuffer:Ue,skinning:z.isSkinnedMesh===!0,morphTargets:V.morphAttributes.position!==void 0,morphNormals:V.morphAttributes.normal!==void 0,morphColors:V.morphAttributes.color!==void 0,morphTargetsCount:Re,morphTextureStride:Ne,numDirLights:b.directional.length,numPointLights:b.point.length,numSpotLights:b.spot.length,numSpotLightMaps:b.spotLightMap.length,numRectAreaLights:b.rectArea.length,numHemiLights:b.hemi.length,numDirLightShadows:b.directionalShadowMap.length,numPointLightShadows:b.pointShadowMap.length,numSpotLightShadows:b.spotShadowMap.length,numSpotLightShadowsWithMaps:b.numSpotLightShadowsWithMaps,numLightProbes:b.numLightProbes,numClippingPlanes:a.numPlanes,numClipIntersection:a.numIntersection,dithering:v.dithering,shadowMapEnabled:i.shadowMap.enabled&&A.length>0,shadowMapType:i.shadowMap.type,toneMapping:He,decodeVideoTexture:bt&&v.map.isVideoTexture===!0&&Je.getTransfer(v.map.colorSpace)===lt,decodeVideoTextureEmissive:ge&&v.emissiveMap.isVideoTexture===!0&&Je.getTransfer(v.emissiveMap.colorSpace)===lt,premultipliedAlpha:v.premultipliedAlpha,doubleSided:v.side===un,flipSided:v.side===jt,useDepthPacking:v.depthPacking>=0,depthPacking:v.depthPacking||0,index0AttributeName:v.index0AttributeName,extensionClipCullDistance:ye&&v.extensions.clipCullDistance===!0&&n.has("WEBGL_clip_cull_distance"),extensionMultiDraw:(ye&&v.extensions.multiDraw===!0||ke)&&n.has("WEBGL_multi_draw"),rendererExtensionParallelShaderCompile:n.has("KHR_parallel_shader_compile"),customProgramCacheKey:v.customProgramCacheKey()};return ft.vertexUv1s=c.has(1),ft.vertexUv2s=c.has(2),ft.vertexUv3s=c.has(3),c.clear(),ft}function m(v){const b=[];if(v.shaderID?b.push(v.shaderID):(b.push(v.customVertexShaderID),b.push(v.customFragmentShaderID)),v.defines!==void 0)for(const A in v.defines)b.push(A),b.push(v.defines[A]);return v.isRawShaderMaterial===!1&&(E(b,v),w(b,v),b.push(i.outputColorSpace)),b.push(v.customProgramCacheKey),b.join()}function E(v,b){v.push(b.precision),v.push(b.outputColorSpace),v.push(b.envMapMode),v.push(b.envMapCubeUVHeight),v.push(b.mapUv),v.push(b.alphaMapUv),v.push(b.lightMapUv),v.push(b.aoMapUv),v.push(b.bumpMapUv),v.push(b.normalMapUv),v.push(b.displacementMapUv),v.push(b.emissiveMapUv),v.push(b.metalnessMapUv),v.push(b.roughnessMapUv),v.push(b.anisotropyMapUv),v.push(b.clearcoatMapUv),v.push(b.clearcoatNormalMapUv),v.push(b.clearcoatRoughnessMapUv),v.push(b.iridescenceMapUv),v.push(b.iridescenceThicknessMapUv),v.push(b.sheenColorMapUv),v.push(b.sheenRoughnessMapUv),v.push(b.specularMapUv),v.push(b.specularColorMapUv),v.push(b.specularIntensityMapUv),v.push(b.transmissionMapUv),v.push(b.thicknessMapUv),v.push(b.combine),v.push(b.fogExp2),v.push(b.sizeAttenuation),v.push(b.morphTargetsCount),v.push(b.morphAttributeCount),v.push(b.numDirLights),v.push(b.numPointLights),v.push(b.numSpotLights),v.push(b.numSpotLightMaps),v.push(b.numHemiLights),v.push(b.numRectAreaLights),v.push(b.numDirLightShadows),v.push(b.numPointLightShadows),v.push(b.numSpotLightShadows),v.push(b.numSpotLightShadowsWithMaps),v.push(b.numLightProbes),v.push(b.shadowMapType),v.push(b.toneMapping),v.push(b.numClippingPlanes),v.push(b.numClipIntersection),v.push(b.depthPacking)}function w(v,b){o.disableAll(),b.supportsVertexTextures&&o.enable(0),b.instancing&&o.enable(1),b.instancingColor&&o.enable(2),b.instancingMorph&&o.enable(3),b.matcap&&o.enable(4),b.envMap&&o.enable(5),b.normalMapObjectSpace&&o.enable(6),b.normalMapTangentSpace&&o.enable(7),b.clearcoat&&o.enable(8),b.iridescence&&o.enable(9),b.alphaTest&&o.enable(10),b.vertexColors&&o.enable(11),b.vertexAlphas&&o.enable(12),b.vertexUv1s&&o.enable(13),b.vertexUv2s&&o.enable(14),b.vertexUv3s&&o.enable(15),b.vertexTangents&&o.enable(16),b.anisotropy&&o.enable(17),b.alphaHash&&o.enable(18),b.batching&&o.enable(19),b.dispersion&&o.enable(20),b.batchingColor&&o.enable(21),b.gradientMap&&o.enable(22),v.push(o.mask),o.disableAll(),b.fog&&o.enable(0),b.useFog&&o.enable(1),b.flatShading&&o.enable(2),b.logarithmicDepthBuffer&&o.enable(3),b.reversedDepthBuffer&&o.enable(4),b.skinning&&o.enable(5),b.morphTargets&&o.enable(6),b.morphNormals&&o.enable(7),b.morphColors&&o.enable(8),b.premultipliedAlpha&&o.enable(9),b.shadowMapEnabled&&o.enable(10),b.doubleSided&&o.enable(11),b.flipSided&&o.enable(12),b.useDepthPacking&&o.enable(13),b.dithering&&o.enable(14),b.transmission&&o.enable(15),b.sheen&&o.enable(16),b.opaque&&o.enable(17),b.pointsUvs&&o.enable(18),b.decodeVideoTexture&&o.enable(19),b.decodeVideoTextureEmissive&&o.enable(20),b.alphaToCoverage&&o.enable(21),v.push(o.mask)}function x(v){const b=_[v.type];let A;if(b){const U=Rn[b];A=Cp.clone(U.uniforms)}else A=v.uniforms;return A}function T(v,b){let A;for(let U=0,z=h.length;U<z;U++){const B=h[U];if(B.cacheKey===b){A=B,++A.usedTimes;break}}return A===void 0&&(A=new Fy(i,b,v,s),h.push(A)),A}function L(v){if(--v.usedTimes===0){const b=h.indexOf(v);h[b]=h[h.length-1],h.pop(),v.destroy()}}function C(v){l.remove(v)}function R(){l.dispose()}return{getParameters:g,getProgramCacheKey:m,getUniforms:x,acquireProgram:T,releaseProgram:L,releaseShaderCache:C,programs:h,dispose:R}}function Hy(){let i=new WeakMap;function e(a){return i.has(a)}function t(a){let o=i.get(a);return o===void 0&&(o={},i.set(a,o)),o}function n(a){i.delete(a)}function r(a,o,l){i.get(a)[o]=l}function s(){i=new WeakMap}return{has:e,get:t,remove:n,update:r,dispose:s}}function Gy(i,e){return i.groupOrder!==e.groupOrder?i.groupOrder-e.groupOrder:i.renderOrder!==e.renderOrder?i.renderOrder-e.renderOrder:i.material.id!==e.material.id?i.material.id-e.material.id:i.z!==e.z?i.z-e.z:i.id-e.id}function iu(i,e){return i.groupOrder!==e.groupOrder?i.groupOrder-e.groupOrder:i.renderOrder!==e.renderOrder?i.renderOrder-e.renderOrder:i.z!==e.z?e.z-i.z:i.id-e.id}function ru(){const i=[];let e=0;const t=[],n=[],r=[];function s(){e=0,t.length=0,n.length=0,r.length=0}function a(u,f,p,_,y,g){let m=i[e];return m===void 0?(m={id:u.id,object:u,geometry:f,material:p,groupOrder:_,renderOrder:u.renderOrder,z:y,group:g},i[e]=m):(m.id=u.id,m.object=u,m.geometry=f,m.material=p,m.groupOrder=_,m.renderOrder=u.renderOrder,m.z=y,m.group=g),e++,m}function o(u,f,p,_,y,g){const m=a(u,f,p,_,y,g);p.transmission>0?n.push(m):p.transparent===!0?r.push(m):t.push(m)}function l(u,f,p,_,y,g){const m=a(u,f,p,_,y,g);p.transmission>0?n.unshift(m):p.transparent===!0?r.unshift(m):t.unshift(m)}function c(u,f){t.length>1&&t.sort(u||Gy),n.length>1&&n.sort(f||iu),r.length>1&&r.sort(f||iu)}function h(){for(let u=e,f=i.length;u<f;u++){const p=i[u];if(p.id===null)break;p.id=null,p.object=null,p.geometry=null,p.material=null,p.group=null}}return{opaque:t,transmissive:n,transparent:r,init:s,push:o,unshift:l,finish:h,sort:c}}function Vy(){let i=new WeakMap;function e(n,r){const s=i.get(n);let a;return s===void 0?(a=new ru,i.set(n,[a])):r>=s.length?(a=new ru,s.push(a)):a=s[r],a}function t(){i=new WeakMap}return{get:e,dispose:t}}function Wy(){const i={};return{get:function(e){if(i[e.id]!==void 0)return i[e.id];let t;switch(e.type){case"DirectionalLight":t={direction:new P,color:new Ee};break;case"SpotLight":t={position:new P,direction:new P,color:new Ee,distance:0,coneCos:0,penumbraCos:0,decay:0};break;case"PointLight":t={position:new P,color:new Ee,distance:0,decay:0};break;case"HemisphereLight":t={direction:new P,skyColor:new Ee,groundColor:new Ee};break;case"RectAreaLight":t={color:new Ee,position:new P,halfWidth:new P,halfHeight:new P};break}return i[e.id]=t,t}}}function Xy(){const i={};return{get:function(e){if(i[e.id]!==void 0)return i[e.id];let t;switch(e.type){case"DirectionalLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new xe};break;case"SpotLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new xe};break;case"PointLight":t={shadowIntensity:1,shadowBias:0,shadowNormalBias:0,shadowRadius:1,shadowMapSize:new xe,shadowCameraNear:1,shadowCameraFar:1e3};break}return i[e.id]=t,t}}}let jy=0;function qy(i,e){return(e.castShadow?2:0)-(i.castShadow?2:0)+(e.map?1:0)-(i.map?1:0)}function Yy(i){const e=new Wy,t=Xy(),n={version:0,hash:{directionalLength:-1,pointLength:-1,spotLength:-1,rectAreaLength:-1,hemiLength:-1,numDirectionalShadows:-1,numPointShadows:-1,numSpotShadows:-1,numSpotMaps:-1,numLightProbes:-1},ambient:[0,0,0],probe:[],directional:[],directionalShadow:[],directionalShadowMap:[],directionalShadowMatrix:[],spot:[],spotLightMap:[],spotShadow:[],spotShadowMap:[],spotLightMatrix:[],rectArea:[],rectAreaLTC1:null,rectAreaLTC2:null,point:[],pointShadow:[],pointShadowMap:[],pointShadowMatrix:[],hemi:[],numSpotLightShadowsWithMaps:0,numLightProbes:0};for(let c=0;c<9;c++)n.probe.push(new P);const r=new P,s=new De,a=new De;function o(c){let h=0,u=0,f=0;for(let v=0;v<9;v++)n.probe[v].set(0,0,0);let p=0,_=0,y=0,g=0,m=0,E=0,w=0,x=0,T=0,L=0,C=0;c.sort(qy);for(let v=0,b=c.length;v<b;v++){const A=c[v],U=A.color,z=A.intensity,B=A.distance,V=A.shadow&&A.shadow.map?A.shadow.map.texture:null;if(A.isAmbientLight)h+=U.r*z,u+=U.g*z,f+=U.b*z;else if(A.isLightProbe){for(let G=0;G<9;G++)n.probe[G].addScaledVector(A.sh.coefficients[G],z);C++}else if(A.isDirectionalLight){const G=e.get(A);if(G.color.copy(A.color).multiplyScalar(A.intensity),A.castShadow){const J=A.shadow,j=t.get(A);j.shadowIntensity=J.intensity,j.shadowBias=J.bias,j.shadowNormalBias=J.normalBias,j.shadowRadius=J.radius,j.shadowMapSize=J.mapSize,n.directionalShadow[p]=j,n.directionalShadowMap[p]=V,n.directionalShadowMatrix[p]=A.shadow.matrix,E++}n.directional[p]=G,p++}else if(A.isSpotLight){const G=e.get(A);G.position.setFromMatrixPosition(A.matrixWorld),G.color.copy(U).multiplyScalar(z),G.distance=B,G.coneCos=Math.cos(A.angle),G.penumbraCos=Math.cos(A.angle*(1-A.penumbra)),G.decay=A.decay,n.spot[y]=G;const J=A.shadow;if(A.map&&(n.spotLightMap[T]=A.map,T++,J.updateMatrices(A),A.castShadow&&L++),n.spotLightMatrix[y]=J.matrix,A.castShadow){const j=t.get(A);j.shadowIntensity=J.intensity,j.shadowBias=J.bias,j.shadowNormalBias=J.normalBias,j.shadowRadius=J.radius,j.shadowMapSize=J.mapSize,n.spotShadow[y]=j,n.spotShadowMap[y]=V,x++}y++}else if(A.isRectAreaLight){const G=e.get(A);G.color.copy(U).multiplyScalar(z),G.halfWidth.set(A.width*.5,0,0),G.halfHeight.set(0,A.height*.5,0),n.rectArea[g]=G,g++}else if(A.isPointLight){const G=e.get(A);if(G.color.copy(A.color).multiplyScalar(A.intensity),G.distance=A.distance,G.decay=A.decay,A.castShadow){const J=A.shadow,j=t.get(A);j.shadowIntensity=J.intensity,j.shadowBias=J.bias,j.shadowNormalBias=J.normalBias,j.shadowRadius=J.radius,j.shadowMapSize=J.mapSize,j.shadowCameraNear=J.camera.near,j.shadowCameraFar=J.camera.far,n.pointShadow[_]=j,n.pointShadowMap[_]=V,n.pointShadowMatrix[_]=A.shadow.matrix,w++}n.point[_]=G,_++}else if(A.isHemisphereLight){const G=e.get(A);G.skyColor.copy(A.color).multiplyScalar(z),G.groundColor.copy(A.groundColor).multiplyScalar(z),n.hemi[m]=G,m++}}g>0&&(i.has("OES_texture_float_linear")===!0?(n.rectAreaLTC1=ce.LTC_FLOAT_1,n.rectAreaLTC2=ce.LTC_FLOAT_2):(n.rectAreaLTC1=ce.LTC_HALF_1,n.rectAreaLTC2=ce.LTC_HALF_2)),n.ambient[0]=h,n.ambient[1]=u,n.ambient[2]=f;const R=n.hash;(R.directionalLength!==p||R.pointLength!==_||R.spotLength!==y||R.rectAreaLength!==g||R.hemiLength!==m||R.numDirectionalShadows!==E||R.numPointShadows!==w||R.numSpotShadows!==x||R.numSpotMaps!==T||R.numLightProbes!==C)&&(n.directional.length=p,n.spot.length=y,n.rectArea.length=g,n.point.length=_,n.hemi.length=m,n.directionalShadow.length=E,n.directionalShadowMap.length=E,n.pointShadow.length=w,n.pointShadowMap.length=w,n.spotShadow.length=x,n.spotShadowMap.length=x,n.directionalShadowMatrix.length=E,n.pointShadowMatrix.length=w,n.spotLightMatrix.length=x+T-L,n.spotLightMap.length=T,n.numSpotLightShadowsWithMaps=L,n.numLightProbes=C,R.directionalLength=p,R.pointLength=_,R.spotLength=y,R.rectAreaLength=g,R.hemiLength=m,R.numDirectionalShadows=E,R.numPointShadows=w,R.numSpotShadows=x,R.numSpotMaps=T,R.numLightProbes=C,n.version=jy++)}function l(c,h){let u=0,f=0,p=0,_=0,y=0;const g=h.matrixWorldInverse;for(let m=0,E=c.length;m<E;m++){const w=c[m];if(w.isDirectionalLight){const x=n.directional[u];x.direction.setFromMatrixPosition(w.matrixWorld),r.setFromMatrixPosition(w.target.matrixWorld),x.direction.sub(r),x.direction.transformDirection(g),u++}else if(w.isSpotLight){const x=n.spot[p];x.position.setFromMatrixPosition(w.matrixWorld),x.position.applyMatrix4(g),x.direction.setFromMatrixPosition(w.matrixWorld),r.setFromMatrixPosition(w.target.matrixWorld),x.direction.sub(r),x.direction.transformDirection(g),p++}else if(w.isRectAreaLight){const x=n.rectArea[_];x.position.setFromMatrixPosition(w.matrixWorld),x.position.applyMatrix4(g),a.identity(),s.copy(w.matrixWorld),s.premultiply(g),a.extractRotation(s),x.halfWidth.set(w.width*.5,0,0),x.halfHeight.set(0,w.height*.5,0),x.halfWidth.applyMatrix4(a),x.halfHeight.applyMatrix4(a),_++}else if(w.isPointLight){const x=n.point[f];x.position.setFromMatrixPosition(w.matrixWorld),x.position.applyMatrix4(g),f++}else if(w.isHemisphereLight){const x=n.hemi[y];x.direction.setFromMatrixPosition(w.matrixWorld),x.direction.transformDirection(g),y++}}}return{setup:o,setupView:l,state:n}}function su(i){const e=new Yy(i),t=[],n=[];function r(h){c.camera=h,t.length=0,n.length=0}function s(h){t.push(h)}function a(h){n.push(h)}function o(){e.setup(t)}function l(h){e.setupView(t,h)}const c={lightsArray:t,shadowsArray:n,camera:null,lights:e,transmissionRenderTarget:{}};return{init:r,state:c,setupLights:o,setupLightsView:l,pushLight:s,pushShadow:a}}function Ky(i){let e=new WeakMap;function t(r,s=0){const a=e.get(r);let o;return a===void 0?(o=new su(i),e.set(r,[o])):s>=a.length?(o=new su(i),a.push(o)):o=a[s],o}function n(){e=new WeakMap}return{get:t,dispose:n}}const $y=`void main() {
	gl_Position = vec4( position, 1.0 );
}`,Zy=`uniform sampler2D shadow_pass;
uniform vec2 resolution;
uniform float radius;
#include <packing>
void main() {
	const float samples = float( VSM_SAMPLES );
	float mean = 0.0;
	float squared_mean = 0.0;
	float uvStride = samples <= 1.0 ? 0.0 : 2.0 / ( samples - 1.0 );
	float uvStart = samples <= 1.0 ? 0.0 : - 1.0;
	for ( float i = 0.0; i < samples; i ++ ) {
		float uvOffset = uvStart + i * uvStride;
		#ifdef HORIZONTAL_PASS
			vec2 distribution = unpackRGBATo2Half( texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( uvOffset, 0.0 ) * radius ) / resolution ) );
			mean += distribution.x;
			squared_mean += distribution.y * distribution.y + distribution.x * distribution.x;
		#else
			float depth = unpackRGBAToDepth( texture2D( shadow_pass, ( gl_FragCoord.xy + vec2( 0.0, uvOffset ) * radius ) / resolution ) );
			mean += depth;
			squared_mean += depth * depth;
		#endif
	}
	mean = mean / samples;
	squared_mean = squared_mean / samples;
	float std_dev = sqrt( squared_mean - mean * mean );
	gl_FragColor = pack2HalfToRGBA( vec2( mean, std_dev ) );
}`;function Jy(i,e,t){let n=new Xa;const r=new xe,s=new xe,a=new Ye,o=new jp({depthPacking:Uf}),l=new qp,c={},h=t.maxTextureSize,u={[ei]:jt,[jt]:ei,[un]:un},f=new ti({defines:{VSM_SAMPLES:8},uniforms:{shadow_pass:{value:null},resolution:{value:new xe},radius:{value:4}},vertexShader:$y,fragmentShader:Zy}),p=f.clone();p.defines.HORIZONTAL_PASS=1;const _=new yt;_.setAttribute("position",new Ot(new Float32Array([-1,-1,.5,3,-1,.5,-1,3,.5]),3));const y=new ut(_,f),g=this;this.enabled=!1,this.autoUpdate=!0,this.needsUpdate=!1,this.type=Eu;let m=this.type;this.render=function(L,C,R){if(g.enabled===!1||g.autoUpdate===!1&&g.needsUpdate===!1||L.length===0)return;const v=i.getRenderTarget(),b=i.getActiveCubeFace(),A=i.getActiveMipmapLevel(),U=i.state;U.setBlending(fi),U.buffers.depth.getReversed()?U.buffers.color.setClear(0,0,0,0):U.buffers.color.setClear(1,1,1,1),U.buffers.depth.setTest(!0),U.setScissorTest(!1);const z=m!==Wn&&this.type===Wn,B=m===Wn&&this.type!==Wn;for(let V=0,G=L.length;V<G;V++){const J=L[V],j=J.shadow;if(j===void 0){console.warn("THREE.WebGLShadowMap:",J,"has no shadow.");continue}if(j.autoUpdate===!1&&j.needsUpdate===!1)continue;r.copy(j.mapSize);const re=j.getFrameExtents();if(r.multiply(re),s.copy(j.mapSize),(r.x>h||r.y>h)&&(r.x>h&&(s.x=Math.floor(h/re.x),r.x=s.x*re.x,j.mapSize.x=s.x),r.y>h&&(s.y=Math.floor(h/re.y),r.y=s.y*re.y,j.mapSize.y=s.y)),j.map===null||z===!0||B===!0){const Re=this.type!==Wn?{minFilter:qt,magFilter:qt}:{};j.map!==null&&j.map.dispose(),j.map=new Ni(r.x,r.y,Re),j.map.texture.name=J.name+".shadowMap",j.camera.updateProjectionMatrix()}i.setRenderTarget(j.map),i.clear();const le=j.getViewportCount();for(let Re=0;Re<le;Re++){const Ne=j.getViewport(Re);a.set(s.x*Ne.x,s.y*Ne.y,s.x*Ne.z,s.y*Ne.w),U.viewport(a),j.updateMatrices(J,Re),n=j.getFrustum(),x(C,R,j.camera,J,this.type)}j.isPointLightShadow!==!0&&this.type===Wn&&E(j,R),j.needsUpdate=!1}m=this.type,g.needsUpdate=!1,i.setRenderTarget(v,b,A)};function E(L,C){const R=e.update(y);f.defines.VSM_SAMPLES!==L.blurSamples&&(f.defines.VSM_SAMPLES=L.blurSamples,p.defines.VSM_SAMPLES=L.blurSamples,f.needsUpdate=!0,p.needsUpdate=!0),L.mapPass===null&&(L.mapPass=new Ni(r.x,r.y)),f.uniforms.shadow_pass.value=L.map.texture,f.uniforms.resolution.value=L.mapSize,f.uniforms.radius.value=L.radius,i.setRenderTarget(L.mapPass),i.clear(),i.renderBufferDirect(C,null,R,f,y,null),p.uniforms.shadow_pass.value=L.mapPass.texture,p.uniforms.resolution.value=L.mapSize,p.uniforms.radius.value=L.radius,i.setRenderTarget(L.map),i.clear(),i.renderBufferDirect(C,null,R,p,y,null)}function w(L,C,R,v){let b=null;const A=R.isPointLight===!0?L.customDistanceMaterial:L.customDepthMaterial;if(A!==void 0)b=A;else if(b=R.isPointLight===!0?l:o,i.localClippingEnabled&&C.clipShadows===!0&&Array.isArray(C.clippingPlanes)&&C.clippingPlanes.length!==0||C.displacementMap&&C.displacementScale!==0||C.alphaMap&&C.alphaTest>0||C.map&&C.alphaTest>0||C.alphaToCoverage===!0){const U=b.uuid,z=C.uuid;let B=c[U];B===void 0&&(B={},c[U]=B);let V=B[z];V===void 0&&(V=b.clone(),B[z]=V,C.addEventListener("dispose",T)),b=V}if(b.visible=C.visible,b.wireframe=C.wireframe,v===Wn?b.side=C.shadowSide!==null?C.shadowSide:C.side:b.side=C.shadowSide!==null?C.shadowSide:u[C.side],b.alphaMap=C.alphaMap,b.alphaTest=C.alphaToCoverage===!0?.5:C.alphaTest,b.map=C.map,b.clipShadows=C.clipShadows,b.clippingPlanes=C.clippingPlanes,b.clipIntersection=C.clipIntersection,b.displacementMap=C.displacementMap,b.displacementScale=C.displacementScale,b.displacementBias=C.displacementBias,b.wireframeLinewidth=C.wireframeLinewidth,b.linewidth=C.linewidth,R.isPointLight===!0&&b.isMeshDistanceMaterial===!0){const U=i.properties.get(b);U.light=R}return b}function x(L,C,R,v,b){if(L.visible===!1)return;if(L.layers.test(C.layers)&&(L.isMesh||L.isLine||L.isPoints)&&(L.castShadow||L.receiveShadow&&b===Wn)&&(!L.frustumCulled||n.intersectsObject(L))){L.modelViewMatrix.multiplyMatrices(R.matrixWorldInverse,L.matrixWorld);const z=e.update(L),B=L.material;if(Array.isArray(B)){const V=z.groups;for(let G=0,J=V.length;G<J;G++){const j=V[G],re=B[j.materialIndex];if(re&&re.visible){const le=w(L,re,v,b);L.onBeforeShadow(i,L,C,R,z,le,j),i.renderBufferDirect(R,null,z,le,L,j),L.onAfterShadow(i,L,C,R,z,le,j)}}}else if(B.visible){const V=w(L,B,v,b);L.onBeforeShadow(i,L,C,R,z,V,null),i.renderBufferDirect(R,null,z,V,L,null),L.onAfterShadow(i,L,C,R,z,V,null)}}const U=L.children;for(let z=0,B=U.length;z<B;z++)x(U[z],C,R,v,b)}function T(L){L.target.removeEventListener("dispose",T);for(const R in c){const v=c[R],b=L.target.uuid;b in v&&(v[b].dispose(),delete v[b])}}}const Qy={[Yo]:Ko,[$o]:Qo,[Zo]:el,[br]:Jo,[Ko]:Yo,[Qo]:$o,[el]:Zo,[Jo]:br};function ex(i,e){function t(){let N=!1;const ie=new Ye;let oe=null;const me=new Ye(0,0,0,0);return{setMask:function(ee){oe!==ee&&!N&&(i.colorMask(ee,ee,ee,ee),oe=ee)},setLocked:function(ee){N=ee},setClear:function(ee,Z,ye,He,ft){ft===!0&&(ee*=He,Z*=He,ye*=He),ie.set(ee,Z,ye,He),me.equals(ie)===!1&&(i.clearColor(ee,Z,ye,He),me.copy(ie))},reset:function(){N=!1,oe=null,me.set(-1,0,0,0)}}}function n(){let N=!1,ie=!1,oe=null,me=null,ee=null;return{setReversed:function(Z){if(ie!==Z){const ye=e.get("EXT_clip_control");Z?ye.clipControlEXT(ye.LOWER_LEFT_EXT,ye.ZERO_TO_ONE_EXT):ye.clipControlEXT(ye.LOWER_LEFT_EXT,ye.NEGATIVE_ONE_TO_ONE_EXT),ie=Z;const He=ee;ee=null,this.setClear(He)}},getReversed:function(){return ie},setTest:function(Z){Z?ae(i.DEPTH_TEST):Ue(i.DEPTH_TEST)},setMask:function(Z){oe!==Z&&!N&&(i.depthMask(Z),oe=Z)},setFunc:function(Z){if(ie&&(Z=Qy[Z]),me!==Z){switch(Z){case Yo:i.depthFunc(i.NEVER);break;case Ko:i.depthFunc(i.ALWAYS);break;case $o:i.depthFunc(i.LESS);break;case br:i.depthFunc(i.LEQUAL);break;case Zo:i.depthFunc(i.EQUAL);break;case Jo:i.depthFunc(i.GEQUAL);break;case Qo:i.depthFunc(i.GREATER);break;case el:i.depthFunc(i.NOTEQUAL);break;default:i.depthFunc(i.LEQUAL)}me=Z}},setLocked:function(Z){N=Z},setClear:function(Z){ee!==Z&&(ie&&(Z=1-Z),i.clearDepth(Z),ee=Z)},reset:function(){N=!1,oe=null,me=null,ee=null,ie=!1}}}function r(){let N=!1,ie=null,oe=null,me=null,ee=null,Z=null,ye=null,He=null,ft=null;return{setTest:function(rt){N||(rt?ae(i.STENCIL_TEST):Ue(i.STENCIL_TEST))},setMask:function(rt){ie!==rt&&!N&&(i.stencilMask(rt),ie=rt)},setFunc:function(rt,On,An){(oe!==rt||me!==On||ee!==An)&&(i.stencilFunc(rt,On,An),oe=rt,me=On,ee=An)},setOp:function(rt,On,An){(Z!==rt||ye!==On||He!==An)&&(i.stencilOp(rt,On,An),Z=rt,ye=On,He=An)},setLocked:function(rt){N=rt},setClear:function(rt){ft!==rt&&(i.clearStencil(rt),ft=rt)},reset:function(){N=!1,ie=null,oe=null,me=null,ee=null,Z=null,ye=null,He=null,ft=null}}}const s=new t,a=new n,o=new r,l=new WeakMap,c=new WeakMap;let h={},u={},f=new WeakMap,p=[],_=null,y=!1,g=null,m=null,E=null,w=null,x=null,T=null,L=null,C=new Ee(0,0,0),R=0,v=!1,b=null,A=null,U=null,z=null,B=null;const V=i.getParameter(i.MAX_COMBINED_TEXTURE_IMAGE_UNITS);let G=!1,J=0;const j=i.getParameter(i.VERSION);j.indexOf("WebGL")!==-1?(J=parseFloat(/^WebGL (\d)/.exec(j)[1]),G=J>=1):j.indexOf("OpenGL ES")!==-1&&(J=parseFloat(/^OpenGL ES (\d)/.exec(j)[1]),G=J>=2);let re=null,le={};const Re=i.getParameter(i.SCISSOR_BOX),Ne=i.getParameter(i.VIEWPORT),Ze=new Ye().fromArray(Re),it=new Ye().fromArray(Ne);function $(N,ie,oe,me){const ee=new Uint8Array(4),Z=i.createTexture();i.bindTexture(N,Z),i.texParameteri(N,i.TEXTURE_MIN_FILTER,i.NEAREST),i.texParameteri(N,i.TEXTURE_MAG_FILTER,i.NEAREST);for(let ye=0;ye<oe;ye++)N===i.TEXTURE_3D||N===i.TEXTURE_2D_ARRAY?i.texImage3D(ie,0,i.RGBA,1,1,me,0,i.RGBA,i.UNSIGNED_BYTE,ee):i.texImage2D(ie+ye,0,i.RGBA,1,1,0,i.RGBA,i.UNSIGNED_BYTE,ee);return Z}const de={};de[i.TEXTURE_2D]=$(i.TEXTURE_2D,i.TEXTURE_2D,1),de[i.TEXTURE_CUBE_MAP]=$(i.TEXTURE_CUBE_MAP,i.TEXTURE_CUBE_MAP_POSITIVE_X,6),de[i.TEXTURE_2D_ARRAY]=$(i.TEXTURE_2D_ARRAY,i.TEXTURE_2D_ARRAY,1,1),de[i.TEXTURE_3D]=$(i.TEXTURE_3D,i.TEXTURE_3D,1,1),s.setClear(0,0,0,1),a.setClear(1),o.setClear(0),ae(i.DEPTH_TEST),a.setFunc(br),nt(!1),Ce(zc),ae(i.CULL_FACE),ht(fi);function ae(N){h[N]!==!0&&(i.enable(N),h[N]=!0)}function Ue(N){h[N]!==!1&&(i.disable(N),h[N]=!1)}function Fe(N,ie){return u[N]!==ie?(i.bindFramebuffer(N,ie),u[N]=ie,N===i.DRAW_FRAMEBUFFER&&(u[i.FRAMEBUFFER]=ie),N===i.FRAMEBUFFER&&(u[i.DRAW_FRAMEBUFFER]=ie),!0):!1}function ke(N,ie){let oe=p,me=!1;if(N){oe=f.get(ie),oe===void 0&&(oe=[],f.set(ie,oe));const ee=N.textures;if(oe.length!==ee.length||oe[0]!==i.COLOR_ATTACHMENT0){for(let Z=0,ye=ee.length;Z<ye;Z++)oe[Z]=i.COLOR_ATTACHMENT0+Z;oe.length=ee.length,me=!0}}else oe[0]!==i.BACK&&(oe[0]=i.BACK,me=!0);me&&i.drawBuffers(oe)}function bt(N){return _!==N?(i.useProgram(N),_=N,!0):!1}const Qe={[Ci]:i.FUNC_ADD,[af]:i.FUNC_SUBTRACT,[of]:i.FUNC_REVERSE_SUBTRACT};Qe[lf]=i.MIN,Qe[cf]=i.MAX;const D={[df]:i.ZERO,[uf]:i.ONE,[hf]:i.SRC_COLOR,[jo]:i.SRC_ALPHA,[yf]:i.SRC_ALPHA_SATURATE,[gf]:i.DST_COLOR,[pf]:i.DST_ALPHA,[ff]:i.ONE_MINUS_SRC_COLOR,[qo]:i.ONE_MINUS_SRC_ALPHA,[_f]:i.ONE_MINUS_DST_COLOR,[mf]:i.ONE_MINUS_DST_ALPHA,[xf]:i.CONSTANT_COLOR,[vf]:i.ONE_MINUS_CONSTANT_COLOR,[Mf]:i.CONSTANT_ALPHA,[bf]:i.ONE_MINUS_CONSTANT_ALPHA};function ht(N,ie,oe,me,ee,Z,ye,He,ft,rt){if(N===fi){y===!0&&(Ue(i.BLEND),y=!1);return}if(y===!1&&(ae(i.BLEND),y=!0),N!==sf){if(N!==g||rt!==v){if((m!==Ci||x!==Ci)&&(i.blendEquation(i.FUNC_ADD),m=Ci,x=Ci),rt)switch(N){case mr:i.blendFuncSeparate(i.ONE,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case kc:i.blendFunc(i.ONE,i.ONE);break;case Hc:i.blendFuncSeparate(i.ZERO,i.ONE_MINUS_SRC_COLOR,i.ZERO,i.ONE);break;case Gc:i.blendFuncSeparate(i.DST_COLOR,i.ONE_MINUS_SRC_ALPHA,i.ZERO,i.ONE);break;default:console.error("THREE.WebGLState: Invalid blending: ",N);break}else switch(N){case mr:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE_MINUS_SRC_ALPHA,i.ONE,i.ONE_MINUS_SRC_ALPHA);break;case kc:i.blendFuncSeparate(i.SRC_ALPHA,i.ONE,i.ONE,i.ONE);break;case Hc:console.error("THREE.WebGLState: SubtractiveBlending requires material.premultipliedAlpha = true");break;case Gc:console.error("THREE.WebGLState: MultiplyBlending requires material.premultipliedAlpha = true");break;default:console.error("THREE.WebGLState: Invalid blending: ",N);break}E=null,w=null,T=null,L=null,C.set(0,0,0),R=0,g=N,v=rt}return}ee=ee||ie,Z=Z||oe,ye=ye||me,(ie!==m||ee!==x)&&(i.blendEquationSeparate(Qe[ie],Qe[ee]),m=ie,x=ee),(oe!==E||me!==w||Z!==T||ye!==L)&&(i.blendFuncSeparate(D[oe],D[me],D[Z],D[ye]),E=oe,w=me,T=Z,L=ye),(He.equals(C)===!1||ft!==R)&&(i.blendColor(He.r,He.g,He.b,ft),C.copy(He),R=ft),g=N,v=!1}function Ie(N,ie){N.side===un?Ue(i.CULL_FACE):ae(i.CULL_FACE);let oe=N.side===jt;ie&&(oe=!oe),nt(oe),N.blending===mr&&N.transparent===!1?ht(fi):ht(N.blending,N.blendEquation,N.blendSrc,N.blendDst,N.blendEquationAlpha,N.blendSrcAlpha,N.blendDstAlpha,N.blendColor,N.blendAlpha,N.premultipliedAlpha),a.setFunc(N.depthFunc),a.setTest(N.depthTest),a.setMask(N.depthWrite),s.setMask(N.colorWrite);const me=N.stencilWrite;o.setTest(me),me&&(o.setMask(N.stencilWriteMask),o.setFunc(N.stencilFunc,N.stencilRef,N.stencilFuncMask),o.setOp(N.stencilFail,N.stencilZFail,N.stencilZPass)),ge(N.polygonOffset,N.polygonOffsetFactor,N.polygonOffsetUnits),N.alphaToCoverage===!0?ae(i.SAMPLE_ALPHA_TO_COVERAGE):Ue(i.SAMPLE_ALPHA_TO_COVERAGE)}function nt(N){b!==N&&(N?i.frontFace(i.CW):i.frontFace(i.CCW),b=N)}function Ce(N){N!==nf?(ae(i.CULL_FACE),N!==A&&(N===zc?i.cullFace(i.BACK):N===rf?i.cullFace(i.FRONT):i.cullFace(i.FRONT_AND_BACK))):Ue(i.CULL_FACE),A=N}function _t(N){N!==U&&(G&&i.lineWidth(N),U=N)}function ge(N,ie,oe){N?(ae(i.POLYGON_OFFSET_FILL),(z!==ie||B!==oe)&&(i.polygonOffset(ie,oe),z=ie,B=oe)):Ue(i.POLYGON_OFFSET_FILL)}function je(N){N?ae(i.SCISSOR_TEST):Ue(i.SCISSOR_TEST)}function Dt(N){N===void 0&&(N=i.TEXTURE0+V-1),re!==N&&(i.activeTexture(N),re=N)}function St(N,ie,oe){oe===void 0&&(re===null?oe=i.TEXTURE0+V-1:oe=re);let me=le[oe];me===void 0&&(me={type:void 0,texture:void 0},le[oe]=me),(me.type!==N||me.texture!==ie)&&(re!==oe&&(i.activeTexture(oe),re=oe),i.bindTexture(N,ie||de[N]),me.type=N,me.texture=ie)}function I(){const N=le[re];N!==void 0&&N.type!==void 0&&(i.bindTexture(N.type,null),N.type=void 0,N.texture=void 0)}function M(){try{i.compressedTexImage2D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function k(){try{i.compressedTexImage3D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function K(){try{i.texSubImage2D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function Q(){try{i.texSubImage3D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function Y(){try{i.compressedTexSubImage2D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function Te(){try{i.compressedTexSubImage3D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function se(){try{i.texStorage2D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function ve(){try{i.texStorage3D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function be(){try{i.texImage2D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function ne(){try{i.texImage3D(...arguments)}catch(N){console.error("THREE.WebGLState:",N)}}function fe(N){Ze.equals(N)===!1&&(i.scissor(N.x,N.y,N.z,N.w),Ze.copy(N))}function Be(N){it.equals(N)===!1&&(i.viewport(N.x,N.y,N.z,N.w),it.copy(N))}function Se(N,ie){let oe=c.get(ie);oe===void 0&&(oe=new WeakMap,c.set(ie,oe));let me=oe.get(N);me===void 0&&(me=i.getUniformBlockIndex(ie,N.name),oe.set(N,me))}function ue(N,ie){const me=c.get(ie).get(N);l.get(ie)!==me&&(i.uniformBlockBinding(ie,me,N.__bindingPointIndex),l.set(ie,me))}function Ge(){i.disable(i.BLEND),i.disable(i.CULL_FACE),i.disable(i.DEPTH_TEST),i.disable(i.POLYGON_OFFSET_FILL),i.disable(i.SCISSOR_TEST),i.disable(i.STENCIL_TEST),i.disable(i.SAMPLE_ALPHA_TO_COVERAGE),i.blendEquation(i.FUNC_ADD),i.blendFunc(i.ONE,i.ZERO),i.blendFuncSeparate(i.ONE,i.ZERO,i.ONE,i.ZERO),i.blendColor(0,0,0,0),i.colorMask(!0,!0,!0,!0),i.clearColor(0,0,0,0),i.depthMask(!0),i.depthFunc(i.LESS),a.setReversed(!1),i.clearDepth(1),i.stencilMask(4294967295),i.stencilFunc(i.ALWAYS,0,4294967295),i.stencilOp(i.KEEP,i.KEEP,i.KEEP),i.clearStencil(0),i.cullFace(i.BACK),i.frontFace(i.CCW),i.polygonOffset(0,0),i.activeTexture(i.TEXTURE0),i.bindFramebuffer(i.FRAMEBUFFER,null),i.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),i.bindFramebuffer(i.READ_FRAMEBUFFER,null),i.useProgram(null),i.lineWidth(1),i.scissor(0,0,i.canvas.width,i.canvas.height),i.viewport(0,0,i.canvas.width,i.canvas.height),h={},re=null,le={},u={},f=new WeakMap,p=[],_=null,y=!1,g=null,m=null,E=null,w=null,x=null,T=null,L=null,C=new Ee(0,0,0),R=0,v=!1,b=null,A=null,U=null,z=null,B=null,Ze.set(0,0,i.canvas.width,i.canvas.height),it.set(0,0,i.canvas.width,i.canvas.height),s.reset(),a.reset(),o.reset()}return{buffers:{color:s,depth:a,stencil:o},enable:ae,disable:Ue,bindFramebuffer:Fe,drawBuffers:ke,useProgram:bt,setBlending:ht,setMaterial:Ie,setFlipSided:nt,setCullFace:Ce,setLineWidth:_t,setPolygonOffset:ge,setScissorTest:je,activeTexture:Dt,bindTexture:St,unbindTexture:I,compressedTexImage2D:M,compressedTexImage3D:k,texImage2D:be,texImage3D:ne,updateUBOMapping:Se,uniformBlockBinding:ue,texStorage2D:se,texStorage3D:ve,texSubImage2D:K,texSubImage3D:Q,compressedTexSubImage2D:Y,compressedTexSubImage3D:Te,scissor:fe,viewport:Be,reset:Ge}}function tx(i,e,t,n,r,s,a){const o=e.has("WEBGL_multisampled_render_to_texture")?e.get("WEBGL_multisampled_render_to_texture"):null,l=typeof navigator>"u"?!1:/OculusBrowser/g.test(navigator.userAgent),c=new xe,h=new WeakMap;let u;const f=new WeakMap;let p=!1;try{p=typeof OffscreenCanvas<"u"&&new OffscreenCanvas(1,1).getContext("2d")!==null}catch{}function _(I,M){return p?new OffscreenCanvas(I,M):ys("canvas")}function y(I,M,k){let K=1;const Q=St(I);if((Q.width>k||Q.height>k)&&(K=k/Math.max(Q.width,Q.height)),K<1)if(typeof HTMLImageElement<"u"&&I instanceof HTMLImageElement||typeof HTMLCanvasElement<"u"&&I instanceof HTMLCanvasElement||typeof ImageBitmap<"u"&&I instanceof ImageBitmap||typeof VideoFrame<"u"&&I instanceof VideoFrame){const Y=Math.floor(K*Q.width),Te=Math.floor(K*Q.height);u===void 0&&(u=_(Y,Te));const se=M?_(Y,Te):u;return se.width=Y,se.height=Te,se.getContext("2d").drawImage(I,0,0,Y,Te),console.warn("THREE.WebGLRenderer: Texture has been resized from ("+Q.width+"x"+Q.height+") to ("+Y+"x"+Te+")."),se}else return"data"in I&&console.warn("THREE.WebGLRenderer: Image in DataTexture is too big ("+Q.width+"x"+Q.height+")."),I;return I}function g(I){return I.generateMipmaps}function m(I){i.generateMipmap(I)}function E(I){return I.isWebGLCubeRenderTarget?i.TEXTURE_CUBE_MAP:I.isWebGL3DRenderTarget?i.TEXTURE_3D:I.isWebGLArrayRenderTarget||I.isCompressedArrayTexture?i.TEXTURE_2D_ARRAY:i.TEXTURE_2D}function w(I,M,k,K,Q=!1){if(I!==null){if(i[I]!==void 0)return i[I];console.warn("THREE.WebGLRenderer: Attempt to use non-existing WebGL internal format '"+I+"'")}let Y=M;if(M===i.RED&&(k===i.FLOAT&&(Y=i.R32F),k===i.HALF_FLOAT&&(Y=i.R16F),k===i.UNSIGNED_BYTE&&(Y=i.R8)),M===i.RED_INTEGER&&(k===i.UNSIGNED_BYTE&&(Y=i.R8UI),k===i.UNSIGNED_SHORT&&(Y=i.R16UI),k===i.UNSIGNED_INT&&(Y=i.R32UI),k===i.BYTE&&(Y=i.R8I),k===i.SHORT&&(Y=i.R16I),k===i.INT&&(Y=i.R32I)),M===i.RG&&(k===i.FLOAT&&(Y=i.RG32F),k===i.HALF_FLOAT&&(Y=i.RG16F),k===i.UNSIGNED_BYTE&&(Y=i.RG8)),M===i.RG_INTEGER&&(k===i.UNSIGNED_BYTE&&(Y=i.RG8UI),k===i.UNSIGNED_SHORT&&(Y=i.RG16UI),k===i.UNSIGNED_INT&&(Y=i.RG32UI),k===i.BYTE&&(Y=i.RG8I),k===i.SHORT&&(Y=i.RG16I),k===i.INT&&(Y=i.RG32I)),M===i.RGB_INTEGER&&(k===i.UNSIGNED_BYTE&&(Y=i.RGB8UI),k===i.UNSIGNED_SHORT&&(Y=i.RGB16UI),k===i.UNSIGNED_INT&&(Y=i.RGB32UI),k===i.BYTE&&(Y=i.RGB8I),k===i.SHORT&&(Y=i.RGB16I),k===i.INT&&(Y=i.RGB32I)),M===i.RGBA_INTEGER&&(k===i.UNSIGNED_BYTE&&(Y=i.RGBA8UI),k===i.UNSIGNED_SHORT&&(Y=i.RGBA16UI),k===i.UNSIGNED_INT&&(Y=i.RGBA32UI),k===i.BYTE&&(Y=i.RGBA8I),k===i.SHORT&&(Y=i.RGBA16I),k===i.INT&&(Y=i.RGBA32I)),M===i.RGB&&k===i.UNSIGNED_INT_5_9_9_9_REV&&(Y=i.RGB9_E5),M===i.RGBA){const Te=Q?Na:Je.getTransfer(K);k===i.FLOAT&&(Y=i.RGBA32F),k===i.HALF_FLOAT&&(Y=i.RGBA16F),k===i.UNSIGNED_BYTE&&(Y=Te===lt?i.SRGB8_ALPHA8:i.RGBA8),k===i.UNSIGNED_SHORT_4_4_4_4&&(Y=i.RGBA4),k===i.UNSIGNED_SHORT_5_5_5_1&&(Y=i.RGB5_A1)}return(Y===i.R16F||Y===i.R32F||Y===i.RG16F||Y===i.RG32F||Y===i.RGBA16F||Y===i.RGBA32F)&&e.get("EXT_color_buffer_float"),Y}function x(I,M){let k;return I?M===null||M===Di||M===fs?k=i.DEPTH24_STENCIL8:M===$t?k=i.DEPTH32F_STENCIL8:M===hs&&(k=i.DEPTH24_STENCIL8,console.warn("DepthTexture: 16 bit depth attachment is not supported with stencil. Using 24-bit attachment.")):M===null||M===Di||M===fs?k=i.DEPTH_COMPONENT24:M===$t?k=i.DEPTH_COMPONENT32F:M===hs&&(k=i.DEPTH_COMPONENT16),k}function T(I,M){return g(I)===!0||I.isFramebufferTexture&&I.minFilter!==qt&&I.minFilter!==Tt?Math.log2(Math.max(M.width,M.height))+1:I.mipmaps!==void 0&&I.mipmaps.length>0?I.mipmaps.length:I.isCompressedTexture&&Array.isArray(I.image)?M.mipmaps.length:1}function L(I){const M=I.target;M.removeEventListener("dispose",L),R(M),M.isVideoTexture&&h.delete(M)}function C(I){const M=I.target;M.removeEventListener("dispose",C),b(M)}function R(I){const M=n.get(I);if(M.__webglInit===void 0)return;const k=I.source,K=f.get(k);if(K){const Q=K[M.__cacheKey];Q.usedTimes--,Q.usedTimes===0&&v(I),Object.keys(K).length===0&&f.delete(k)}n.remove(I)}function v(I){const M=n.get(I);i.deleteTexture(M.__webglTexture);const k=I.source,K=f.get(k);delete K[M.__cacheKey],a.memory.textures--}function b(I){const M=n.get(I);if(I.depthTexture&&(I.depthTexture.dispose(),n.remove(I.depthTexture)),I.isWebGLCubeRenderTarget)for(let K=0;K<6;K++){if(Array.isArray(M.__webglFramebuffer[K]))for(let Q=0;Q<M.__webglFramebuffer[K].length;Q++)i.deleteFramebuffer(M.__webglFramebuffer[K][Q]);else i.deleteFramebuffer(M.__webglFramebuffer[K]);M.__webglDepthbuffer&&i.deleteRenderbuffer(M.__webglDepthbuffer[K])}else{if(Array.isArray(M.__webglFramebuffer))for(let K=0;K<M.__webglFramebuffer.length;K++)i.deleteFramebuffer(M.__webglFramebuffer[K]);else i.deleteFramebuffer(M.__webglFramebuffer);if(M.__webglDepthbuffer&&i.deleteRenderbuffer(M.__webglDepthbuffer),M.__webglMultisampledFramebuffer&&i.deleteFramebuffer(M.__webglMultisampledFramebuffer),M.__webglColorRenderbuffer)for(let K=0;K<M.__webglColorRenderbuffer.length;K++)M.__webglColorRenderbuffer[K]&&i.deleteRenderbuffer(M.__webglColorRenderbuffer[K]);M.__webglDepthRenderbuffer&&i.deleteRenderbuffer(M.__webglDepthRenderbuffer)}const k=I.textures;for(let K=0,Q=k.length;K<Q;K++){const Y=n.get(k[K]);Y.__webglTexture&&(i.deleteTexture(Y.__webglTexture),a.memory.textures--),n.remove(k[K])}n.remove(I)}let A=0;function U(){A=0}function z(){const I=A;return I>=r.maxTextures&&console.warn("THREE.WebGLTextures: Trying to use "+I+" texture units while this GPU supports only "+r.maxTextures),A+=1,I}function B(I){const M=[];return M.push(I.wrapS),M.push(I.wrapT),M.push(I.wrapR||0),M.push(I.magFilter),M.push(I.minFilter),M.push(I.anisotropy),M.push(I.internalFormat),M.push(I.format),M.push(I.type),M.push(I.generateMipmaps),M.push(I.premultiplyAlpha),M.push(I.flipY),M.push(I.unpackAlignment),M.push(I.colorSpace),M.join()}function V(I,M){const k=n.get(I);if(I.isVideoTexture&&je(I),I.isRenderTargetTexture===!1&&I.isExternalTexture!==!0&&I.version>0&&k.__version!==I.version){const K=I.image;if(K===null)console.warn("THREE.WebGLRenderer: Texture marked for update but no image data found.");else if(K.complete===!1)console.warn("THREE.WebGLRenderer: Texture marked for update but image is incomplete");else{de(k,I,M);return}}else I.isExternalTexture&&(k.__webglTexture=I.sourceTexture?I.sourceTexture:null);t.bindTexture(i.TEXTURE_2D,k.__webglTexture,i.TEXTURE0+M)}function G(I,M){const k=n.get(I);if(I.isRenderTargetTexture===!1&&I.version>0&&k.__version!==I.version){de(k,I,M);return}t.bindTexture(i.TEXTURE_2D_ARRAY,k.__webglTexture,i.TEXTURE0+M)}function J(I,M){const k=n.get(I);if(I.isRenderTargetTexture===!1&&I.version>0&&k.__version!==I.version){de(k,I,M);return}t.bindTexture(i.TEXTURE_3D,k.__webglTexture,i.TEXTURE0+M)}function j(I,M){const k=n.get(I);if(I.version>0&&k.__version!==I.version){ae(k,I,M);return}t.bindTexture(i.TEXTURE_CUBE_MAP,k.__webglTexture,i.TEXTURE0+M)}const re={[_i]:i.REPEAT,[Cn]:i.CLAMP_TO_EDGE,[Da]:i.MIRRORED_REPEAT},le={[qt]:i.NEAREST,[Cu]:i.NEAREST_MIPMAP_NEAREST,[ts]:i.NEAREST_MIPMAP_LINEAR,[Tt]:i.LINEAR,[xa]:i.LINEAR_MIPMAP_NEAREST,[Pn]:i.LINEAR_MIPMAP_LINEAR},Re={[Of]:i.NEVER,[Vf]:i.ALWAYS,[Bf]:i.LESS,[Bu]:i.LEQUAL,[zf]:i.EQUAL,[Gf]:i.GEQUAL,[kf]:i.GREATER,[Hf]:i.NOTEQUAL};function Ne(I,M){if(M.type===$t&&e.has("OES_texture_float_linear")===!1&&(M.magFilter===Tt||M.magFilter===xa||M.magFilter===ts||M.magFilter===Pn||M.minFilter===Tt||M.minFilter===xa||M.minFilter===ts||M.minFilter===Pn)&&console.warn("THREE.WebGLRenderer: Unable to use linear filtering with floating point textures. OES_texture_float_linear not supported on this device."),i.texParameteri(I,i.TEXTURE_WRAP_S,re[M.wrapS]),i.texParameteri(I,i.TEXTURE_WRAP_T,re[M.wrapT]),(I===i.TEXTURE_3D||I===i.TEXTURE_2D_ARRAY)&&i.texParameteri(I,i.TEXTURE_WRAP_R,re[M.wrapR]),i.texParameteri(I,i.TEXTURE_MAG_FILTER,le[M.magFilter]),i.texParameteri(I,i.TEXTURE_MIN_FILTER,le[M.minFilter]),M.compareFunction&&(i.texParameteri(I,i.TEXTURE_COMPARE_MODE,i.COMPARE_REF_TO_TEXTURE),i.texParameteri(I,i.TEXTURE_COMPARE_FUNC,Re[M.compareFunction])),e.has("EXT_texture_filter_anisotropic")===!0){if(M.magFilter===qt||M.minFilter!==ts&&M.minFilter!==Pn||M.type===$t&&e.has("OES_texture_float_linear")===!1)return;if(M.anisotropy>1||n.get(M).__currentAnisotropy){const k=e.get("EXT_texture_filter_anisotropic");i.texParameterf(I,k.TEXTURE_MAX_ANISOTROPY_EXT,Math.min(M.anisotropy,r.getMaxAnisotropy())),n.get(M).__currentAnisotropy=M.anisotropy}}}function Ze(I,M){let k=!1;I.__webglInit===void 0&&(I.__webglInit=!0,M.addEventListener("dispose",L));const K=M.source;let Q=f.get(K);Q===void 0&&(Q={},f.set(K,Q));const Y=B(M);if(Y!==I.__cacheKey){Q[Y]===void 0&&(Q[Y]={texture:i.createTexture(),usedTimes:0},a.memory.textures++,k=!0),Q[Y].usedTimes++;const Te=Q[I.__cacheKey];Te!==void 0&&(Q[I.__cacheKey].usedTimes--,Te.usedTimes===0&&v(M)),I.__cacheKey=Y,I.__webglTexture=Q[Y].texture}return k}function it(I,M,k){return Math.floor(Math.floor(I/k)/M)}function $(I,M,k,K){const Y=I.updateRanges;if(Y.length===0)t.texSubImage2D(i.TEXTURE_2D,0,0,0,M.width,M.height,k,K,M.data);else{Y.sort((ne,fe)=>ne.start-fe.start);let Te=0;for(let ne=1;ne<Y.length;ne++){const fe=Y[Te],Be=Y[ne],Se=fe.start+fe.count,ue=it(Be.start,M.width,4),Ge=it(fe.start,M.width,4);Be.start<=Se+1&&ue===Ge&&it(Be.start+Be.count-1,M.width,4)===ue?fe.count=Math.max(fe.count,Be.start+Be.count-fe.start):(++Te,Y[Te]=Be)}Y.length=Te+1;const se=i.getParameter(i.UNPACK_ROW_LENGTH),ve=i.getParameter(i.UNPACK_SKIP_PIXELS),be=i.getParameter(i.UNPACK_SKIP_ROWS);i.pixelStorei(i.UNPACK_ROW_LENGTH,M.width);for(let ne=0,fe=Y.length;ne<fe;ne++){const Be=Y[ne],Se=Math.floor(Be.start/4),ue=Math.ceil(Be.count/4),Ge=Se%M.width,N=Math.floor(Se/M.width),ie=ue,oe=1;i.pixelStorei(i.UNPACK_SKIP_PIXELS,Ge),i.pixelStorei(i.UNPACK_SKIP_ROWS,N),t.texSubImage2D(i.TEXTURE_2D,0,Ge,N,ie,oe,k,K,M.data)}I.clearUpdateRanges(),i.pixelStorei(i.UNPACK_ROW_LENGTH,se),i.pixelStorei(i.UNPACK_SKIP_PIXELS,ve),i.pixelStorei(i.UNPACK_SKIP_ROWS,be)}}function de(I,M,k){let K=i.TEXTURE_2D;(M.isDataArrayTexture||M.isCompressedArrayTexture)&&(K=i.TEXTURE_2D_ARRAY),M.isData3DTexture&&(K=i.TEXTURE_3D);const Q=Ze(I,M),Y=M.source;t.bindTexture(K,I.__webglTexture,i.TEXTURE0+k);const Te=n.get(Y);if(Y.version!==Te.__version||Q===!0){t.activeTexture(i.TEXTURE0+k);const se=Je.getPrimaries(Je.workingColorSpace),ve=M.colorSpace===hi?null:Je.getPrimaries(M.colorSpace),be=M.colorSpace===hi||se===ve?i.NONE:i.BROWSER_DEFAULT_WEBGL;i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,M.flipY),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,M.premultiplyAlpha),i.pixelStorei(i.UNPACK_ALIGNMENT,M.unpackAlignment),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,be);let ne=y(M.image,!1,r.maxTextureSize);ne=Dt(M,ne);const fe=s.convert(M.format,M.colorSpace),Be=s.convert(M.type);let Se=w(M.internalFormat,fe,Be,M.colorSpace,M.isVideoTexture);Ne(K,M);let ue;const Ge=M.mipmaps,N=M.isVideoTexture!==!0,ie=Te.__version===void 0||Q===!0,oe=Y.dataReady,me=T(M,ne);if(M.isDepthTexture)Se=x(M.format===ms,M.type),ie&&(N?t.texStorage2D(i.TEXTURE_2D,1,Se,ne.width,ne.height):t.texImage2D(i.TEXTURE_2D,0,Se,ne.width,ne.height,0,fe,Be,null));else if(M.isDataTexture)if(Ge.length>0){N&&ie&&t.texStorage2D(i.TEXTURE_2D,me,Se,Ge[0].width,Ge[0].height);for(let ee=0,Z=Ge.length;ee<Z;ee++)ue=Ge[ee],N?oe&&t.texSubImage2D(i.TEXTURE_2D,ee,0,0,ue.width,ue.height,fe,Be,ue.data):t.texImage2D(i.TEXTURE_2D,ee,Se,ue.width,ue.height,0,fe,Be,ue.data);M.generateMipmaps=!1}else N?(ie&&t.texStorage2D(i.TEXTURE_2D,me,Se,ne.width,ne.height),oe&&$(M,ne,fe,Be)):t.texImage2D(i.TEXTURE_2D,0,Se,ne.width,ne.height,0,fe,Be,ne.data);else if(M.isCompressedTexture)if(M.isCompressedArrayTexture){N&&ie&&t.texStorage3D(i.TEXTURE_2D_ARRAY,me,Se,Ge[0].width,Ge[0].height,ne.depth);for(let ee=0,Z=Ge.length;ee<Z;ee++)if(ue=Ge[ee],M.format!==sn)if(fe!==null)if(N){if(oe)if(M.layerUpdates.size>0){const ye=Fd(ue.width,ue.height,M.format,M.type);for(const He of M.layerUpdates){const ft=ue.data.subarray(He*ye/ue.data.BYTES_PER_ELEMENT,(He+1)*ye/ue.data.BYTES_PER_ELEMENT);t.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,ee,0,0,He,ue.width,ue.height,1,fe,ft)}M.clearLayerUpdates()}else t.compressedTexSubImage3D(i.TEXTURE_2D_ARRAY,ee,0,0,0,ue.width,ue.height,ne.depth,fe,ue.data)}else t.compressedTexImage3D(i.TEXTURE_2D_ARRAY,ee,Se,ue.width,ue.height,ne.depth,0,ue.data,0,0);else console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()");else N?oe&&t.texSubImage3D(i.TEXTURE_2D_ARRAY,ee,0,0,0,ue.width,ue.height,ne.depth,fe,Be,ue.data):t.texImage3D(i.TEXTURE_2D_ARRAY,ee,Se,ue.width,ue.height,ne.depth,0,fe,Be,ue.data)}else{N&&ie&&t.texStorage2D(i.TEXTURE_2D,me,Se,Ge[0].width,Ge[0].height);for(let ee=0,Z=Ge.length;ee<Z;ee++)ue=Ge[ee],M.format!==sn?fe!==null?N?oe&&t.compressedTexSubImage2D(i.TEXTURE_2D,ee,0,0,ue.width,ue.height,fe,ue.data):t.compressedTexImage2D(i.TEXTURE_2D,ee,Se,ue.width,ue.height,0,ue.data):console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .uploadTexture()"):N?oe&&t.texSubImage2D(i.TEXTURE_2D,ee,0,0,ue.width,ue.height,fe,Be,ue.data):t.texImage2D(i.TEXTURE_2D,ee,Se,ue.width,ue.height,0,fe,Be,ue.data)}else if(M.isDataArrayTexture)if(N){if(ie&&t.texStorage3D(i.TEXTURE_2D_ARRAY,me,Se,ne.width,ne.height,ne.depth),oe)if(M.layerUpdates.size>0){const ee=Fd(ne.width,ne.height,M.format,M.type);for(const Z of M.layerUpdates){const ye=ne.data.subarray(Z*ee/ne.data.BYTES_PER_ELEMENT,(Z+1)*ee/ne.data.BYTES_PER_ELEMENT);t.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,Z,ne.width,ne.height,1,fe,Be,ye)}M.clearLayerUpdates()}else t.texSubImage3D(i.TEXTURE_2D_ARRAY,0,0,0,0,ne.width,ne.height,ne.depth,fe,Be,ne.data)}else t.texImage3D(i.TEXTURE_2D_ARRAY,0,Se,ne.width,ne.height,ne.depth,0,fe,Be,ne.data);else if(M.isData3DTexture)N?(ie&&t.texStorage3D(i.TEXTURE_3D,me,Se,ne.width,ne.height,ne.depth),oe&&t.texSubImage3D(i.TEXTURE_3D,0,0,0,0,ne.width,ne.height,ne.depth,fe,Be,ne.data)):t.texImage3D(i.TEXTURE_3D,0,Se,ne.width,ne.height,ne.depth,0,fe,Be,ne.data);else if(M.isFramebufferTexture){if(ie)if(N)t.texStorage2D(i.TEXTURE_2D,me,Se,ne.width,ne.height);else{let ee=ne.width,Z=ne.height;for(let ye=0;ye<me;ye++)t.texImage2D(i.TEXTURE_2D,ye,Se,ee,Z,0,fe,Be,null),ee>>=1,Z>>=1}}else if(Ge.length>0){if(N&&ie){const ee=St(Ge[0]);t.texStorage2D(i.TEXTURE_2D,me,Se,ee.width,ee.height)}for(let ee=0,Z=Ge.length;ee<Z;ee++)ue=Ge[ee],N?oe&&t.texSubImage2D(i.TEXTURE_2D,ee,0,0,fe,Be,ue):t.texImage2D(i.TEXTURE_2D,ee,Se,fe,Be,ue);M.generateMipmaps=!1}else if(N){if(ie){const ee=St(ne);t.texStorage2D(i.TEXTURE_2D,me,Se,ee.width,ee.height)}oe&&t.texSubImage2D(i.TEXTURE_2D,0,0,0,fe,Be,ne)}else t.texImage2D(i.TEXTURE_2D,0,Se,fe,Be,ne);g(M)&&m(K),Te.__version=Y.version,M.onUpdate&&M.onUpdate(M)}I.__version=M.version}function ae(I,M,k){if(M.image.length!==6)return;const K=Ze(I,M),Q=M.source;t.bindTexture(i.TEXTURE_CUBE_MAP,I.__webglTexture,i.TEXTURE0+k);const Y=n.get(Q);if(Q.version!==Y.__version||K===!0){t.activeTexture(i.TEXTURE0+k);const Te=Je.getPrimaries(Je.workingColorSpace),se=M.colorSpace===hi?null:Je.getPrimaries(M.colorSpace),ve=M.colorSpace===hi||Te===se?i.NONE:i.BROWSER_DEFAULT_WEBGL;i.pixelStorei(i.UNPACK_FLIP_Y_WEBGL,M.flipY),i.pixelStorei(i.UNPACK_PREMULTIPLY_ALPHA_WEBGL,M.premultiplyAlpha),i.pixelStorei(i.UNPACK_ALIGNMENT,M.unpackAlignment),i.pixelStorei(i.UNPACK_COLORSPACE_CONVERSION_WEBGL,ve);const be=M.isCompressedTexture||M.image[0].isCompressedTexture,ne=M.image[0]&&M.image[0].isDataTexture,fe=[];for(let Z=0;Z<6;Z++)!be&&!ne?fe[Z]=y(M.image[Z],!0,r.maxCubemapSize):fe[Z]=ne?M.image[Z].image:M.image[Z],fe[Z]=Dt(M,fe[Z]);const Be=fe[0],Se=s.convert(M.format,M.colorSpace),ue=s.convert(M.type),Ge=w(M.internalFormat,Se,ue,M.colorSpace),N=M.isVideoTexture!==!0,ie=Y.__version===void 0||K===!0,oe=Q.dataReady;let me=T(M,Be);Ne(i.TEXTURE_CUBE_MAP,M);let ee;if(be){N&&ie&&t.texStorage2D(i.TEXTURE_CUBE_MAP,me,Ge,Be.width,Be.height);for(let Z=0;Z<6;Z++){ee=fe[Z].mipmaps;for(let ye=0;ye<ee.length;ye++){const He=ee[ye];M.format!==sn?Se!==null?N?oe&&t.compressedTexSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye,0,0,He.width,He.height,Se,He.data):t.compressedTexImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye,Ge,He.width,He.height,0,He.data):console.warn("THREE.WebGLRenderer: Attempt to load unsupported compressed texture format in .setTextureCube()"):N?oe&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye,0,0,He.width,He.height,Se,ue,He.data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye,Ge,He.width,He.height,0,Se,ue,He.data)}}}else{if(ee=M.mipmaps,N&&ie){ee.length>0&&me++;const Z=St(fe[0]);t.texStorage2D(i.TEXTURE_CUBE_MAP,me,Ge,Z.width,Z.height)}for(let Z=0;Z<6;Z++)if(ne){N?oe&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,0,0,0,fe[Z].width,fe[Z].height,Se,ue,fe[Z].data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,0,Ge,fe[Z].width,fe[Z].height,0,Se,ue,fe[Z].data);for(let ye=0;ye<ee.length;ye++){const ft=ee[ye].image[Z].image;N?oe&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye+1,0,0,ft.width,ft.height,Se,ue,ft.data):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye+1,Ge,ft.width,ft.height,0,Se,ue,ft.data)}}else{N?oe&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,0,0,0,Se,ue,fe[Z]):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,0,Ge,Se,ue,fe[Z]);for(let ye=0;ye<ee.length;ye++){const He=ee[ye];N?oe&&t.texSubImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye+1,0,0,Se,ue,He.image[Z]):t.texImage2D(i.TEXTURE_CUBE_MAP_POSITIVE_X+Z,ye+1,Ge,Se,ue,He.image[Z])}}}g(M)&&m(i.TEXTURE_CUBE_MAP),Y.__version=Q.version,M.onUpdate&&M.onUpdate(M)}I.__version=M.version}function Ue(I,M,k,K,Q,Y){const Te=s.convert(k.format,k.colorSpace),se=s.convert(k.type),ve=w(k.internalFormat,Te,se,k.colorSpace),be=n.get(M),ne=n.get(k);if(ne.__renderTarget=M,!be.__hasExternalTextures){const fe=Math.max(1,M.width>>Y),Be=Math.max(1,M.height>>Y);Q===i.TEXTURE_3D||Q===i.TEXTURE_2D_ARRAY?t.texImage3D(Q,Y,ve,fe,Be,M.depth,0,Te,se,null):t.texImage2D(Q,Y,ve,fe,Be,0,Te,se,null)}t.bindFramebuffer(i.FRAMEBUFFER,I),ge(M)?o.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,K,Q,ne.__webglTexture,0,_t(M)):(Q===i.TEXTURE_2D||Q>=i.TEXTURE_CUBE_MAP_POSITIVE_X&&Q<=i.TEXTURE_CUBE_MAP_NEGATIVE_Z)&&i.framebufferTexture2D(i.FRAMEBUFFER,K,Q,ne.__webglTexture,Y),t.bindFramebuffer(i.FRAMEBUFFER,null)}function Fe(I,M,k){if(i.bindRenderbuffer(i.RENDERBUFFER,I),M.depthBuffer){const K=M.depthTexture,Q=K&&K.isDepthTexture?K.type:null,Y=x(M.stencilBuffer,Q),Te=M.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,se=_t(M);ge(M)?o.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,se,Y,M.width,M.height):k?i.renderbufferStorageMultisample(i.RENDERBUFFER,se,Y,M.width,M.height):i.renderbufferStorage(i.RENDERBUFFER,Y,M.width,M.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,Te,i.RENDERBUFFER,I)}else{const K=M.textures;for(let Q=0;Q<K.length;Q++){const Y=K[Q],Te=s.convert(Y.format,Y.colorSpace),se=s.convert(Y.type),ve=w(Y.internalFormat,Te,se,Y.colorSpace),be=_t(M);k&&ge(M)===!1?i.renderbufferStorageMultisample(i.RENDERBUFFER,be,ve,M.width,M.height):ge(M)?o.renderbufferStorageMultisampleEXT(i.RENDERBUFFER,be,ve,M.width,M.height):i.renderbufferStorage(i.RENDERBUFFER,ve,M.width,M.height)}}i.bindRenderbuffer(i.RENDERBUFFER,null)}function ke(I,M){if(M&&M.isWebGLCubeRenderTarget)throw new Error("Depth Texture with cube render targets is not supported");if(t.bindFramebuffer(i.FRAMEBUFFER,I),!(M.depthTexture&&M.depthTexture.isDepthTexture))throw new Error("renderTarget.depthTexture must be an instance of THREE.DepthTexture");const K=n.get(M.depthTexture);K.__renderTarget=M,(!K.__webglTexture||M.depthTexture.image.width!==M.width||M.depthTexture.image.height!==M.height)&&(M.depthTexture.image.width=M.width,M.depthTexture.image.height=M.height,M.depthTexture.needsUpdate=!0),V(M.depthTexture,0);const Q=K.__webglTexture,Y=_t(M);if(M.depthTexture.format===ps)ge(M)?o.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,i.DEPTH_ATTACHMENT,i.TEXTURE_2D,Q,0,Y):i.framebufferTexture2D(i.FRAMEBUFFER,i.DEPTH_ATTACHMENT,i.TEXTURE_2D,Q,0);else if(M.depthTexture.format===ms)ge(M)?o.framebufferTexture2DMultisampleEXT(i.FRAMEBUFFER,i.DEPTH_STENCIL_ATTACHMENT,i.TEXTURE_2D,Q,0,Y):i.framebufferTexture2D(i.FRAMEBUFFER,i.DEPTH_STENCIL_ATTACHMENT,i.TEXTURE_2D,Q,0);else throw new Error("Unknown depthTexture format")}function bt(I){const M=n.get(I),k=I.isWebGLCubeRenderTarget===!0;if(M.__boundDepthTexture!==I.depthTexture){const K=I.depthTexture;if(M.__depthDisposeCallback&&M.__depthDisposeCallback(),K){const Q=()=>{delete M.__boundDepthTexture,delete M.__depthDisposeCallback,K.removeEventListener("dispose",Q)};K.addEventListener("dispose",Q),M.__depthDisposeCallback=Q}M.__boundDepthTexture=K}if(I.depthTexture&&!M.__autoAllocateDepthBuffer){if(k)throw new Error("target.depthTexture not supported in Cube render targets");const K=I.texture.mipmaps;K&&K.length>0?ke(M.__webglFramebuffer[0],I):ke(M.__webglFramebuffer,I)}else if(k){M.__webglDepthbuffer=[];for(let K=0;K<6;K++)if(t.bindFramebuffer(i.FRAMEBUFFER,M.__webglFramebuffer[K]),M.__webglDepthbuffer[K]===void 0)M.__webglDepthbuffer[K]=i.createRenderbuffer(),Fe(M.__webglDepthbuffer[K],I,!1);else{const Q=I.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,Y=M.__webglDepthbuffer[K];i.bindRenderbuffer(i.RENDERBUFFER,Y),i.framebufferRenderbuffer(i.FRAMEBUFFER,Q,i.RENDERBUFFER,Y)}}else{const K=I.texture.mipmaps;if(K&&K.length>0?t.bindFramebuffer(i.FRAMEBUFFER,M.__webglFramebuffer[0]):t.bindFramebuffer(i.FRAMEBUFFER,M.__webglFramebuffer),M.__webglDepthbuffer===void 0)M.__webglDepthbuffer=i.createRenderbuffer(),Fe(M.__webglDepthbuffer,I,!1);else{const Q=I.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,Y=M.__webglDepthbuffer;i.bindRenderbuffer(i.RENDERBUFFER,Y),i.framebufferRenderbuffer(i.FRAMEBUFFER,Q,i.RENDERBUFFER,Y)}}t.bindFramebuffer(i.FRAMEBUFFER,null)}function Qe(I,M,k){const K=n.get(I);M!==void 0&&Ue(K.__webglFramebuffer,I,I.texture,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,0),k!==void 0&&bt(I)}function D(I){const M=I.texture,k=n.get(I),K=n.get(M);I.addEventListener("dispose",C);const Q=I.textures,Y=I.isWebGLCubeRenderTarget===!0,Te=Q.length>1;if(Te||(K.__webglTexture===void 0&&(K.__webglTexture=i.createTexture()),K.__version=M.version,a.memory.textures++),Y){k.__webglFramebuffer=[];for(let se=0;se<6;se++)if(M.mipmaps&&M.mipmaps.length>0){k.__webglFramebuffer[se]=[];for(let ve=0;ve<M.mipmaps.length;ve++)k.__webglFramebuffer[se][ve]=i.createFramebuffer()}else k.__webglFramebuffer[se]=i.createFramebuffer()}else{if(M.mipmaps&&M.mipmaps.length>0){k.__webglFramebuffer=[];for(let se=0;se<M.mipmaps.length;se++)k.__webglFramebuffer[se]=i.createFramebuffer()}else k.__webglFramebuffer=i.createFramebuffer();if(Te)for(let se=0,ve=Q.length;se<ve;se++){const be=n.get(Q[se]);be.__webglTexture===void 0&&(be.__webglTexture=i.createTexture(),a.memory.textures++)}if(I.samples>0&&ge(I)===!1){k.__webglMultisampledFramebuffer=i.createFramebuffer(),k.__webglColorRenderbuffer=[],t.bindFramebuffer(i.FRAMEBUFFER,k.__webglMultisampledFramebuffer);for(let se=0;se<Q.length;se++){const ve=Q[se];k.__webglColorRenderbuffer[se]=i.createRenderbuffer(),i.bindRenderbuffer(i.RENDERBUFFER,k.__webglColorRenderbuffer[se]);const be=s.convert(ve.format,ve.colorSpace),ne=s.convert(ve.type),fe=w(ve.internalFormat,be,ne,ve.colorSpace,I.isXRRenderTarget===!0),Be=_t(I);i.renderbufferStorageMultisample(i.RENDERBUFFER,Be,fe,I.width,I.height),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+se,i.RENDERBUFFER,k.__webglColorRenderbuffer[se])}i.bindRenderbuffer(i.RENDERBUFFER,null),I.depthBuffer&&(k.__webglDepthRenderbuffer=i.createRenderbuffer(),Fe(k.__webglDepthRenderbuffer,I,!0)),t.bindFramebuffer(i.FRAMEBUFFER,null)}}if(Y){t.bindTexture(i.TEXTURE_CUBE_MAP,K.__webglTexture),Ne(i.TEXTURE_CUBE_MAP,M);for(let se=0;se<6;se++)if(M.mipmaps&&M.mipmaps.length>0)for(let ve=0;ve<M.mipmaps.length;ve++)Ue(k.__webglFramebuffer[se][ve],I,M,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+se,ve);else Ue(k.__webglFramebuffer[se],I,M,i.COLOR_ATTACHMENT0,i.TEXTURE_CUBE_MAP_POSITIVE_X+se,0);g(M)&&m(i.TEXTURE_CUBE_MAP),t.unbindTexture()}else if(Te){for(let se=0,ve=Q.length;se<ve;se++){const be=Q[se],ne=n.get(be);let fe=i.TEXTURE_2D;(I.isWebGL3DRenderTarget||I.isWebGLArrayRenderTarget)&&(fe=I.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),t.bindTexture(fe,ne.__webglTexture),Ne(fe,be),Ue(k.__webglFramebuffer,I,be,i.COLOR_ATTACHMENT0+se,fe,0),g(be)&&m(fe)}t.unbindTexture()}else{let se=i.TEXTURE_2D;if((I.isWebGL3DRenderTarget||I.isWebGLArrayRenderTarget)&&(se=I.isWebGL3DRenderTarget?i.TEXTURE_3D:i.TEXTURE_2D_ARRAY),t.bindTexture(se,K.__webglTexture),Ne(se,M),M.mipmaps&&M.mipmaps.length>0)for(let ve=0;ve<M.mipmaps.length;ve++)Ue(k.__webglFramebuffer[ve],I,M,i.COLOR_ATTACHMENT0,se,ve);else Ue(k.__webglFramebuffer,I,M,i.COLOR_ATTACHMENT0,se,0);g(M)&&m(se),t.unbindTexture()}I.depthBuffer&&bt(I)}function ht(I){const M=I.textures;for(let k=0,K=M.length;k<K;k++){const Q=M[k];if(g(Q)){const Y=E(I),Te=n.get(Q).__webglTexture;t.bindTexture(Y,Te),m(Y),t.unbindTexture()}}}const Ie=[],nt=[];function Ce(I){if(I.samples>0){if(ge(I)===!1){const M=I.textures,k=I.width,K=I.height;let Q=i.COLOR_BUFFER_BIT;const Y=I.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT,Te=n.get(I),se=M.length>1;if(se)for(let be=0;be<M.length;be++)t.bindFramebuffer(i.FRAMEBUFFER,Te.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+be,i.RENDERBUFFER,null),t.bindFramebuffer(i.FRAMEBUFFER,Te.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+be,i.TEXTURE_2D,null,0);t.bindFramebuffer(i.READ_FRAMEBUFFER,Te.__webglMultisampledFramebuffer);const ve=I.texture.mipmaps;ve&&ve.length>0?t.bindFramebuffer(i.DRAW_FRAMEBUFFER,Te.__webglFramebuffer[0]):t.bindFramebuffer(i.DRAW_FRAMEBUFFER,Te.__webglFramebuffer);for(let be=0;be<M.length;be++){if(I.resolveDepthBuffer&&(I.depthBuffer&&(Q|=i.DEPTH_BUFFER_BIT),I.stencilBuffer&&I.resolveStencilBuffer&&(Q|=i.STENCIL_BUFFER_BIT)),se){i.framebufferRenderbuffer(i.READ_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.RENDERBUFFER,Te.__webglColorRenderbuffer[be]);const ne=n.get(M[be]).__webglTexture;i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0,i.TEXTURE_2D,ne,0)}i.blitFramebuffer(0,0,k,K,0,0,k,K,Q,i.NEAREST),l===!0&&(Ie.length=0,nt.length=0,Ie.push(i.COLOR_ATTACHMENT0+be),I.depthBuffer&&I.resolveDepthBuffer===!1&&(Ie.push(Y),nt.push(Y),i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,nt)),i.invalidateFramebuffer(i.READ_FRAMEBUFFER,Ie))}if(t.bindFramebuffer(i.READ_FRAMEBUFFER,null),t.bindFramebuffer(i.DRAW_FRAMEBUFFER,null),se)for(let be=0;be<M.length;be++){t.bindFramebuffer(i.FRAMEBUFFER,Te.__webglMultisampledFramebuffer),i.framebufferRenderbuffer(i.FRAMEBUFFER,i.COLOR_ATTACHMENT0+be,i.RENDERBUFFER,Te.__webglColorRenderbuffer[be]);const ne=n.get(M[be]).__webglTexture;t.bindFramebuffer(i.FRAMEBUFFER,Te.__webglFramebuffer),i.framebufferTexture2D(i.DRAW_FRAMEBUFFER,i.COLOR_ATTACHMENT0+be,i.TEXTURE_2D,ne,0)}t.bindFramebuffer(i.DRAW_FRAMEBUFFER,Te.__webglMultisampledFramebuffer)}else if(I.depthBuffer&&I.resolveDepthBuffer===!1&&l){const M=I.stencilBuffer?i.DEPTH_STENCIL_ATTACHMENT:i.DEPTH_ATTACHMENT;i.invalidateFramebuffer(i.DRAW_FRAMEBUFFER,[M])}}}function _t(I){return Math.min(r.maxSamples,I.samples)}function ge(I){const M=n.get(I);return I.samples>0&&e.has("WEBGL_multisampled_render_to_texture")===!0&&M.__useRenderToTexture!==!1}function je(I){const M=a.render.frame;h.get(I)!==M&&(h.set(I,M),I.update())}function Dt(I,M){const k=I.colorSpace,K=I.format,Q=I.type;return I.isCompressedTexture===!0||I.isVideoTexture===!0||k!==zt&&k!==hi&&(Je.getTransfer(k)===lt?(K!==sn||Q!==Sn)&&console.warn("THREE.WebGLTextures: sRGB encoded textures have to use RGBAFormat and UnsignedByteType."):console.error("THREE.WebGLTextures: Unsupported texture color space:",k)),M}function St(I){return typeof HTMLImageElement<"u"&&I instanceof HTMLImageElement?(c.width=I.naturalWidth||I.width,c.height=I.naturalHeight||I.height):typeof VideoFrame<"u"&&I instanceof VideoFrame?(c.width=I.displayWidth,c.height=I.displayHeight):(c.width=I.width,c.height=I.height),c}this.allocateTextureUnit=z,this.resetTextureUnits=U,this.setTexture2D=V,this.setTexture2DArray=G,this.setTexture3D=J,this.setTextureCube=j,this.rebindTextures=Qe,this.setupRenderTarget=D,this.updateRenderTargetMipmap=ht,this.updateMultisampleRenderTarget=Ce,this.setupDepthRenderbuffer=bt,this.setupFrameBufferTexture=Ue,this.useMultisampledRTT=ge}function nx(i,e){function t(n,r=hi){let s;const a=Je.getTransfer(r);if(n===Sn)return i.UNSIGNED_BYTE;if(n===ql)return i.UNSIGNED_SHORT_4_4_4_4;if(n===Yl)return i.UNSIGNED_SHORT_5_5_5_1;if(n===Lu)return i.UNSIGNED_INT_5_9_9_9_REV;if(n===Pu)return i.BYTE;if(n===Iu)return i.SHORT;if(n===hs)return i.UNSIGNED_SHORT;if(n===jl)return i.INT;if(n===Di)return i.UNSIGNED_INT;if(n===$t)return i.FLOAT;if(n===In)return i.HALF_FLOAT;if(n===Du)return i.ALPHA;if(n===Nu)return i.RGB;if(n===sn)return i.RGBA;if(n===ps)return i.DEPTH_COMPONENT;if(n===ms)return i.DEPTH_STENCIL;if(n===Kl)return i.RED;if(n===$l)return i.RED_INTEGER;if(n===Uu)return i.RG;if(n===Zl)return i.RG_INTEGER;if(n===Jl)return i.RGBA_INTEGER;if(n===va||n===Ma||n===ba||n===Sa)if(a===lt)if(s=e.get("WEBGL_compressed_texture_s3tc_srgb"),s!==null){if(n===va)return s.COMPRESSED_SRGB_S3TC_DXT1_EXT;if(n===Ma)return s.COMPRESSED_SRGB_ALPHA_S3TC_DXT1_EXT;if(n===ba)return s.COMPRESSED_SRGB_ALPHA_S3TC_DXT3_EXT;if(n===Sa)return s.COMPRESSED_SRGB_ALPHA_S3TC_DXT5_EXT}else return null;else if(s=e.get("WEBGL_compressed_texture_s3tc"),s!==null){if(n===va)return s.COMPRESSED_RGB_S3TC_DXT1_EXT;if(n===Ma)return s.COMPRESSED_RGBA_S3TC_DXT1_EXT;if(n===ba)return s.COMPRESSED_RGBA_S3TC_DXT3_EXT;if(n===Sa)return s.COMPRESSED_RGBA_S3TC_DXT5_EXT}else return null;if(n===nl||n===il||n===rl||n===sl)if(s=e.get("WEBGL_compressed_texture_pvrtc"),s!==null){if(n===nl)return s.COMPRESSED_RGB_PVRTC_4BPPV1_IMG;if(n===il)return s.COMPRESSED_RGB_PVRTC_2BPPV1_IMG;if(n===rl)return s.COMPRESSED_RGBA_PVRTC_4BPPV1_IMG;if(n===sl)return s.COMPRESSED_RGBA_PVRTC_2BPPV1_IMG}else return null;if(n===al||n===ol||n===ll)if(s=e.get("WEBGL_compressed_texture_etc"),s!==null){if(n===al||n===ol)return a===lt?s.COMPRESSED_SRGB8_ETC2:s.COMPRESSED_RGB8_ETC2;if(n===ll)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ETC2_EAC:s.COMPRESSED_RGBA8_ETC2_EAC}else return null;if(n===cl||n===dl||n===ul||n===hl||n===fl||n===pl||n===ml||n===gl||n===_l||n===yl||n===xl||n===vl||n===Ml||n===bl)if(s=e.get("WEBGL_compressed_texture_astc"),s!==null){if(n===cl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_4x4_KHR:s.COMPRESSED_RGBA_ASTC_4x4_KHR;if(n===dl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_5x4_KHR:s.COMPRESSED_RGBA_ASTC_5x4_KHR;if(n===ul)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_5x5_KHR:s.COMPRESSED_RGBA_ASTC_5x5_KHR;if(n===hl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_6x5_KHR:s.COMPRESSED_RGBA_ASTC_6x5_KHR;if(n===fl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_6x6_KHR:s.COMPRESSED_RGBA_ASTC_6x6_KHR;if(n===pl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_8x5_KHR:s.COMPRESSED_RGBA_ASTC_8x5_KHR;if(n===ml)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_8x6_KHR:s.COMPRESSED_RGBA_ASTC_8x6_KHR;if(n===gl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_8x8_KHR:s.COMPRESSED_RGBA_ASTC_8x8_KHR;if(n===_l)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x5_KHR:s.COMPRESSED_RGBA_ASTC_10x5_KHR;if(n===yl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x6_KHR:s.COMPRESSED_RGBA_ASTC_10x6_KHR;if(n===xl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x8_KHR:s.COMPRESSED_RGBA_ASTC_10x8_KHR;if(n===vl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_10x10_KHR:s.COMPRESSED_RGBA_ASTC_10x10_KHR;if(n===Ml)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_12x10_KHR:s.COMPRESSED_RGBA_ASTC_12x10_KHR;if(n===bl)return a===lt?s.COMPRESSED_SRGB8_ALPHA8_ASTC_12x12_KHR:s.COMPRESSED_RGBA_ASTC_12x12_KHR}else return null;if(n===wa||n===Sl||n===wl)if(s=e.get("EXT_texture_compression_bptc"),s!==null){if(n===wa)return a===lt?s.COMPRESSED_SRGB_ALPHA_BPTC_UNORM_EXT:s.COMPRESSED_RGBA_BPTC_UNORM_EXT;if(n===Sl)return s.COMPRESSED_RGB_BPTC_SIGNED_FLOAT_EXT;if(n===wl)return s.COMPRESSED_RGB_BPTC_UNSIGNED_FLOAT_EXT}else return null;if(n===Fu||n===El||n===Tl||n===Al)if(s=e.get("EXT_texture_compression_rgtc"),s!==null){if(n===wa)return s.COMPRESSED_RED_RGTC1_EXT;if(n===El)return s.COMPRESSED_SIGNED_RED_RGTC1_EXT;if(n===Tl)return s.COMPRESSED_RED_GREEN_RGTC2_EXT;if(n===Al)return s.COMPRESSED_SIGNED_RED_GREEN_RGTC2_EXT}else return null;return n===fs?i.UNSIGNED_INT_24_8:i[n]!==void 0?i[n]:null}return{convert:t}}class hh extends Ct{constructor(e=null){super(),this.sourceTexture=e,this.isExternalTexture=!0}}const ix=`
void main() {

	gl_Position = vec4( position, 1.0 );

}`,rx=`
uniform sampler2DArray depthColor;
uniform float depthWidth;
uniform float depthHeight;

void main() {

	vec2 coord = vec2( gl_FragCoord.x / depthWidth, gl_FragCoord.y / depthHeight );

	if ( coord.x >= 1.0 ) {

		gl_FragDepth = texture( depthColor, vec3( coord.x - 1.0, coord.y, 1 ) ).r;

	} else {

		gl_FragDepth = texture( depthColor, vec3( coord.x, coord.y, 0 ) ).r;

	}

}`;class sx{constructor(){this.texture=null,this.mesh=null,this.depthNear=0,this.depthFar=0}init(e,t){if(this.texture===null){const n=new hh(e.texture);(e.depthNear!==t.depthNear||e.depthFar!==t.depthFar)&&(this.depthNear=e.depthNear,this.depthFar=e.depthFar),this.texture=n}}getMesh(e){if(this.texture!==null&&this.mesh===null){const t=e.cameras[0].viewport,n=new ti({vertexShader:ix,fragmentShader:rx,uniforms:{depthColor:{value:this.texture},depthWidth:{value:t.z},depthHeight:{value:t.w}}});this.mesh=new ut(new Ss(20,20),n)}return this.mesh}reset(){this.texture=null,this.mesh=null}getDepthTexture(){return this.texture}}class ax extends Oi{constructor(e,t){super();const n=this;let r=null,s=1,a=null,o="local-floor",l=1,c=null,h=null,u=null,f=null,p=null,_=null;const y=new sx,g={},m=t.getContextAttributes();let E=null,w=null;const x=[],T=[],L=new xe;let C=null;const R=new Xt;R.viewport=new Ye;const v=new Xt;v.viewport=new Ye;const b=[R,v],A=new gm;let U=null,z=null;this.cameraAutoUpdate=!0,this.enabled=!1,this.isPresenting=!1,this.getController=function($){let de=x[$];return de===void 0&&(de=new wo,x[$]=de),de.getTargetRaySpace()},this.getControllerGrip=function($){let de=x[$];return de===void 0&&(de=new wo,x[$]=de),de.getGripSpace()},this.getHand=function($){let de=x[$];return de===void 0&&(de=new wo,x[$]=de),de.getHandSpace()};function B($){const de=T.indexOf($.inputSource);if(de===-1)return;const ae=x[de];ae!==void 0&&(ae.update($.inputSource,$.frame,c||a),ae.dispatchEvent({type:$.type,data:$.inputSource}))}function V(){r.removeEventListener("select",B),r.removeEventListener("selectstart",B),r.removeEventListener("selectend",B),r.removeEventListener("squeeze",B),r.removeEventListener("squeezestart",B),r.removeEventListener("squeezeend",B),r.removeEventListener("end",V),r.removeEventListener("inputsourceschange",G);for(let $=0;$<x.length;$++){const de=T[$];de!==null&&(T[$]=null,x[$].disconnect(de))}U=null,z=null,y.reset();for(const $ in g)delete g[$];e.setRenderTarget(E),p=null,f=null,u=null,r=null,w=null,it.stop(),n.isPresenting=!1,e.setPixelRatio(C),e.setSize(L.width,L.height,!1),n.dispatchEvent({type:"sessionend"})}this.setFramebufferScaleFactor=function($){s=$,n.isPresenting===!0&&console.warn("THREE.WebXRManager: Cannot change framebuffer scale while presenting.")},this.setReferenceSpaceType=function($){o=$,n.isPresenting===!0&&console.warn("THREE.WebXRManager: Cannot change reference space type while presenting.")},this.getReferenceSpace=function(){return c||a},this.setReferenceSpace=function($){c=$},this.getBaseLayer=function(){return f!==null?f:p},this.getBinding=function(){return u},this.getFrame=function(){return _},this.getSession=function(){return r},this.setSession=async function($){if(r=$,r!==null){if(E=e.getRenderTarget(),r.addEventListener("select",B),r.addEventListener("selectstart",B),r.addEventListener("selectend",B),r.addEventListener("squeeze",B),r.addEventListener("squeezestart",B),r.addEventListener("squeezeend",B),r.addEventListener("end",V),r.addEventListener("inputsourceschange",G),m.xrCompatible!==!0&&await t.makeXRCompatible(),C=e.getPixelRatio(),e.getSize(L),typeof XRWebGLBinding<"u"&&(u=new XRWebGLBinding(r,t)),u!==null&&"createProjectionLayer"in XRWebGLBinding.prototype){let ae=null,Ue=null,Fe=null;m.depth&&(Fe=m.stencil?t.DEPTH24_STENCIL8:t.DEPTH_COMPONENT24,ae=m.stencil?ms:ps,Ue=m.stencil?fs:Di);const ke={colorFormat:t.RGBA8,depthFormat:Fe,scaleFactor:s};f=u.createProjectionLayer(ke),r.updateRenderState({layers:[f]}),e.setPixelRatio(1),e.setSize(f.textureWidth,f.textureHeight,!1),w=new Ni(f.textureWidth,f.textureHeight,{format:sn,type:Sn,depthTexture:new Qu(f.textureWidth,f.textureHeight,Ue,void 0,void 0,void 0,void 0,void 0,void 0,ae),stencilBuffer:m.stencil,colorSpace:e.outputColorSpace,samples:m.antialias?4:0,resolveDepthBuffer:f.ignoreDepthValues===!1,resolveStencilBuffer:f.ignoreDepthValues===!1})}else{const ae={antialias:m.antialias,alpha:!0,depth:m.depth,stencil:m.stencil,framebufferScaleFactor:s};p=new XRWebGLLayer(r,t,ae),r.updateRenderState({baseLayer:p}),e.setPixelRatio(1),e.setSize(p.framebufferWidth,p.framebufferHeight,!1),w=new Ni(p.framebufferWidth,p.framebufferHeight,{format:sn,type:Sn,colorSpace:e.outputColorSpace,stencilBuffer:m.stencil,resolveDepthBuffer:p.ignoreDepthValues===!1,resolveStencilBuffer:p.ignoreDepthValues===!1})}w.isXRRenderTarget=!0,this.setFoveation(l),c=null,a=await r.requestReferenceSpace(o),it.setContext(r),it.start(),n.isPresenting=!0,n.dispatchEvent({type:"sessionstart"})}},this.getEnvironmentBlendMode=function(){if(r!==null)return r.environmentBlendMode},this.getDepthTexture=function(){return y.getDepthTexture()};function G($){for(let de=0;de<$.removed.length;de++){const ae=$.removed[de],Ue=T.indexOf(ae);Ue>=0&&(T[Ue]=null,x[Ue].disconnect(ae))}for(let de=0;de<$.added.length;de++){const ae=$.added[de];let Ue=T.indexOf(ae);if(Ue===-1){for(let ke=0;ke<x.length;ke++)if(ke>=T.length){T.push(ae),Ue=ke;break}else if(T[ke]===null){T[ke]=ae,Ue=ke;break}if(Ue===-1)break}const Fe=x[Ue];Fe&&Fe.connect(ae)}}const J=new P,j=new P;function re($,de,ae){J.setFromMatrixPosition(de.matrixWorld),j.setFromMatrixPosition(ae.matrixWorld);const Ue=J.distanceTo(j),Fe=de.projectionMatrix.elements,ke=ae.projectionMatrix.elements,bt=Fe[14]/(Fe[10]-1),Qe=Fe[14]/(Fe[10]+1),D=(Fe[9]+1)/Fe[5],ht=(Fe[9]-1)/Fe[5],Ie=(Fe[8]-1)/Fe[0],nt=(ke[8]+1)/ke[0],Ce=bt*Ie,_t=bt*nt,ge=Ue/(-Ie+nt),je=ge*-Ie;if(de.matrixWorld.decompose($.position,$.quaternion,$.scale),$.translateX(je),$.translateZ(ge),$.matrixWorld.compose($.position,$.quaternion,$.scale),$.matrixWorldInverse.copy($.matrixWorld).invert(),Fe[10]===-1)$.projectionMatrix.copy(de.projectionMatrix),$.projectionMatrixInverse.copy(de.projectionMatrixInverse);else{const Dt=bt+ge,St=Qe+ge,I=Ce-je,M=_t+(Ue-je),k=D*Qe/St*Dt,K=ht*Qe/St*Dt;$.projectionMatrix.makePerspective(I,M,k,K,Dt,St),$.projectionMatrixInverse.copy($.projectionMatrix).invert()}}function le($,de){de===null?$.matrixWorld.copy($.matrix):$.matrixWorld.multiplyMatrices(de.matrixWorld,$.matrix),$.matrixWorldInverse.copy($.matrixWorld).invert()}this.updateCamera=function($){if(r===null)return;let de=$.near,ae=$.far;y.texture!==null&&(y.depthNear>0&&(de=y.depthNear),y.depthFar>0&&(ae=y.depthFar)),A.near=v.near=R.near=de,A.far=v.far=R.far=ae,(U!==A.near||z!==A.far)&&(r.updateRenderState({depthNear:A.near,depthFar:A.far}),U=A.near,z=A.far),A.layers.mask=$.layers.mask|6,R.layers.mask=A.layers.mask&3,v.layers.mask=A.layers.mask&5;const Ue=$.parent,Fe=A.cameras;le(A,Ue);for(let ke=0;ke<Fe.length;ke++)le(Fe[ke],Ue);Fe.length===2?re(A,R,v):A.projectionMatrix.copy(R.projectionMatrix),Re($,A,Ue)};function Re($,de,ae){ae===null?$.matrix.copy(de.matrixWorld):($.matrix.copy(ae.matrixWorld),$.matrix.invert(),$.matrix.multiply(de.matrixWorld)),$.matrix.decompose($.position,$.quaternion,$.scale),$.updateMatrixWorld(!0),$.projectionMatrix.copy(de.projectionMatrix),$.projectionMatrixInverse.copy(de.projectionMatrixInverse),$.isPerspectiveCamera&&($.fov=Er*2*Math.atan(1/$.projectionMatrix.elements[5]),$.zoom=1)}this.getCamera=function(){return A},this.getFoveation=function(){if(!(f===null&&p===null))return l},this.setFoveation=function($){l=$,f!==null&&(f.fixedFoveation=$),p!==null&&p.fixedFoveation!==void 0&&(p.fixedFoveation=$)},this.hasDepthSensing=function(){return y.texture!==null},this.getDepthSensingMesh=function(){return y.getMesh(A)},this.getCameraTexture=function($){return g[$]};let Ne=null;function Ze($,de){if(h=de.getViewerPose(c||a),_=de,h!==null){const ae=h.views;p!==null&&(e.setRenderTargetFramebuffer(w,p.framebuffer),e.setRenderTarget(w));let Ue=!1;ae.length!==A.cameras.length&&(A.cameras.length=0,Ue=!0);for(let Qe=0;Qe<ae.length;Qe++){const D=ae[Qe];let ht=null;if(p!==null)ht=p.getViewport(D);else{const nt=u.getViewSubImage(f,D);ht=nt.viewport,Qe===0&&(e.setRenderTargetTextures(w,nt.colorTexture,nt.depthStencilTexture),e.setRenderTarget(w))}let Ie=b[Qe];Ie===void 0&&(Ie=new Xt,Ie.layers.enable(Qe),Ie.viewport=new Ye,b[Qe]=Ie),Ie.matrix.fromArray(D.transform.matrix),Ie.matrix.decompose(Ie.position,Ie.quaternion,Ie.scale),Ie.projectionMatrix.fromArray(D.projectionMatrix),Ie.projectionMatrixInverse.copy(Ie.projectionMatrix).invert(),Ie.viewport.set(ht.x,ht.y,ht.width,ht.height),Qe===0&&(A.matrix.copy(Ie.matrix),A.matrix.decompose(A.position,A.quaternion,A.scale)),Ue===!0&&A.cameras.push(Ie)}const Fe=r.enabledFeatures;if(Fe&&Fe.includes("depth-sensing")&&r.depthUsage=="gpu-optimized"&&u){const Qe=u.getDepthInformation(ae[0]);Qe&&Qe.isValid&&Qe.texture&&y.init(Qe,r.renderState)}if(Fe&&Fe.includes("camera-access")&&(e.state.unbindTexture(),u))for(let Qe=0;Qe<ae.length;Qe++){const D=ae[Qe].camera;if(D){let ht=g[D];ht||(ht=new hh,g[D]=ht);const Ie=u.getCameraImage(D);ht.sourceTexture=Ie}}}for(let ae=0;ae<x.length;ae++){const Ue=T[ae],Fe=x[ae];Ue!==null&&Fe!==void 0&&Fe.update(Ue,de,c||a)}Ne&&Ne($,de),de.detectedPlanes&&n.dispatchEvent({type:"planesdetected",data:de}),_=null}const it=new oh;it.setAnimationLoop(Ze),this.setAnimationLoop=function($){Ne=$},this.dispose=function(){}}}const Ti=new pn,ox=new De;function lx(i,e){function t(g,m){g.matrixAutoUpdate===!0&&g.updateMatrix(),m.value.copy(g.matrix)}function n(g,m){m.color.getRGB(g.fogColor.value,Wu(i)),m.isFog?(g.fogNear.value=m.near,g.fogFar.value=m.far):m.isFogExp2&&(g.fogDensity.value=m.density)}function r(g,m,E,w,x){m.isMeshBasicMaterial||m.isMeshLambertMaterial?s(g,m):m.isMeshToonMaterial?(s(g,m),u(g,m)):m.isMeshPhongMaterial?(s(g,m),h(g,m)):m.isMeshStandardMaterial?(s(g,m),f(g,m),m.isMeshPhysicalMaterial&&p(g,m,x)):m.isMeshMatcapMaterial?(s(g,m),_(g,m)):m.isMeshDepthMaterial?s(g,m):m.isMeshDistanceMaterial?(s(g,m),y(g,m)):m.isMeshNormalMaterial?s(g,m):m.isLineBasicMaterial?(a(g,m),m.isLineDashedMaterial&&o(g,m)):m.isPointsMaterial?l(g,m,E,w):m.isSpriteMaterial?c(g,m):m.isShadowMaterial?(g.color.value.copy(m.color),g.opacity.value=m.opacity):m.isShaderMaterial&&(m.uniformsNeedUpdate=!1)}function s(g,m){g.opacity.value=m.opacity,m.color&&g.diffuse.value.copy(m.color),m.emissive&&g.emissive.value.copy(m.emissive).multiplyScalar(m.emissiveIntensity),m.map&&(g.map.value=m.map,t(m.map,g.mapTransform)),m.alphaMap&&(g.alphaMap.value=m.alphaMap,t(m.alphaMap,g.alphaMapTransform)),m.bumpMap&&(g.bumpMap.value=m.bumpMap,t(m.bumpMap,g.bumpMapTransform),g.bumpScale.value=m.bumpScale,m.side===jt&&(g.bumpScale.value*=-1)),m.normalMap&&(g.normalMap.value=m.normalMap,t(m.normalMap,g.normalMapTransform),g.normalScale.value.copy(m.normalScale),m.side===jt&&g.normalScale.value.negate()),m.displacementMap&&(g.displacementMap.value=m.displacementMap,t(m.displacementMap,g.displacementMapTransform),g.displacementScale.value=m.displacementScale,g.displacementBias.value=m.displacementBias),m.emissiveMap&&(g.emissiveMap.value=m.emissiveMap,t(m.emissiveMap,g.emissiveMapTransform)),m.specularMap&&(g.specularMap.value=m.specularMap,t(m.specularMap,g.specularMapTransform)),m.alphaTest>0&&(g.alphaTest.value=m.alphaTest);const E=e.get(m),w=E.envMap,x=E.envMapRotation;w&&(g.envMap.value=w,Ti.copy(x),Ti.x*=-1,Ti.y*=-1,Ti.z*=-1,w.isCubeTexture&&w.isRenderTargetTexture===!1&&(Ti.y*=-1,Ti.z*=-1),g.envMapRotation.value.setFromMatrix4(ox.makeRotationFromEuler(Ti)),g.flipEnvMap.value=w.isCubeTexture&&w.isRenderTargetTexture===!1?-1:1,g.reflectivity.value=m.reflectivity,g.ior.value=m.ior,g.refractionRatio.value=m.refractionRatio),m.lightMap&&(g.lightMap.value=m.lightMap,g.lightMapIntensity.value=m.lightMapIntensity,t(m.lightMap,g.lightMapTransform)),m.aoMap&&(g.aoMap.value=m.aoMap,g.aoMapIntensity.value=m.aoMapIntensity,t(m.aoMap,g.aoMapTransform))}function a(g,m){g.diffuse.value.copy(m.color),g.opacity.value=m.opacity,m.map&&(g.map.value=m.map,t(m.map,g.mapTransform))}function o(g,m){g.dashSize.value=m.dashSize,g.totalSize.value=m.dashSize+m.gapSize,g.scale.value=m.scale}function l(g,m,E,w){g.diffuse.value.copy(m.color),g.opacity.value=m.opacity,g.size.value=m.size*E,g.scale.value=w*.5,m.map&&(g.map.value=m.map,t(m.map,g.uvTransform)),m.alphaMap&&(g.alphaMap.value=m.alphaMap,t(m.alphaMap,g.alphaMapTransform)),m.alphaTest>0&&(g.alphaTest.value=m.alphaTest)}function c(g,m){g.diffuse.value.copy(m.color),g.opacity.value=m.opacity,g.rotation.value=m.rotation,m.map&&(g.map.value=m.map,t(m.map,g.mapTransform)),m.alphaMap&&(g.alphaMap.value=m.alphaMap,t(m.alphaMap,g.alphaMapTransform)),m.alphaTest>0&&(g.alphaTest.value=m.alphaTest)}function h(g,m){g.specular.value.copy(m.specular),g.shininess.value=Math.max(m.shininess,1e-4)}function u(g,m){m.gradientMap&&(g.gradientMap.value=m.gradientMap)}function f(g,m){g.metalness.value=m.metalness,m.metalnessMap&&(g.metalnessMap.value=m.metalnessMap,t(m.metalnessMap,g.metalnessMapTransform)),g.roughness.value=m.roughness,m.roughnessMap&&(g.roughnessMap.value=m.roughnessMap,t(m.roughnessMap,g.roughnessMapTransform)),m.envMap&&(g.envMapIntensity.value=m.envMapIntensity)}function p(g,m,E){g.ior.value=m.ior,m.sheen>0&&(g.sheenColor.value.copy(m.sheenColor).multiplyScalar(m.sheen),g.sheenRoughness.value=m.sheenRoughness,m.sheenColorMap&&(g.sheenColorMap.value=m.sheenColorMap,t(m.sheenColorMap,g.sheenColorMapTransform)),m.sheenRoughnessMap&&(g.sheenRoughnessMap.value=m.sheenRoughnessMap,t(m.sheenRoughnessMap,g.sheenRoughnessMapTransform))),m.clearcoat>0&&(g.clearcoat.value=m.clearcoat,g.clearcoatRoughness.value=m.clearcoatRoughness,m.clearcoatMap&&(g.clearcoatMap.value=m.clearcoatMap,t(m.clearcoatMap,g.clearcoatMapTransform)),m.clearcoatRoughnessMap&&(g.clearcoatRoughnessMap.value=m.clearcoatRoughnessMap,t(m.clearcoatRoughnessMap,g.clearcoatRoughnessMapTransform)),m.clearcoatNormalMap&&(g.clearcoatNormalMap.value=m.clearcoatNormalMap,t(m.clearcoatNormalMap,g.clearcoatNormalMapTransform),g.clearcoatNormalScale.value.copy(m.clearcoatNormalScale),m.side===jt&&g.clearcoatNormalScale.value.negate())),m.dispersion>0&&(g.dispersion.value=m.dispersion),m.iridescence>0&&(g.iridescence.value=m.iridescence,g.iridescenceIOR.value=m.iridescenceIOR,g.iridescenceThicknessMinimum.value=m.iridescenceThicknessRange[0],g.iridescenceThicknessMaximum.value=m.iridescenceThicknessRange[1],m.iridescenceMap&&(g.iridescenceMap.value=m.iridescenceMap,t(m.iridescenceMap,g.iridescenceMapTransform)),m.iridescenceThicknessMap&&(g.iridescenceThicknessMap.value=m.iridescenceThicknessMap,t(m.iridescenceThicknessMap,g.iridescenceThicknessMapTransform))),m.transmission>0&&(g.transmission.value=m.transmission,g.transmissionSamplerMap.value=E.texture,g.transmissionSamplerSize.value.set(E.width,E.height),m.transmissionMap&&(g.transmissionMap.value=m.transmissionMap,t(m.transmissionMap,g.transmissionMapTransform)),g.thickness.value=m.thickness,m.thicknessMap&&(g.thicknessMap.value=m.thicknessMap,t(m.thicknessMap,g.thicknessMapTransform)),g.attenuationDistance.value=m.attenuationDistance,g.attenuationColor.value.copy(m.attenuationColor)),m.anisotropy>0&&(g.anisotropyVector.value.set(m.anisotropy*Math.cos(m.anisotropyRotation),m.anisotropy*Math.sin(m.anisotropyRotation)),m.anisotropyMap&&(g.anisotropyMap.value=m.anisotropyMap,t(m.anisotropyMap,g.anisotropyMapTransform))),g.specularIntensity.value=m.specularIntensity,g.specularColor.value.copy(m.specularColor),m.specularColorMap&&(g.specularColorMap.value=m.specularColorMap,t(m.specularColorMap,g.specularColorMapTransform)),m.specularIntensityMap&&(g.specularIntensityMap.value=m.specularIntensityMap,t(m.specularIntensityMap,g.specularIntensityMapTransform))}function _(g,m){m.matcap&&(g.matcap.value=m.matcap)}function y(g,m){const E=e.get(m).light;g.referencePosition.value.setFromMatrixPosition(E.matrixWorld),g.nearDistance.value=E.shadow.camera.near,g.farDistance.value=E.shadow.camera.far}return{refreshFogUniforms:n,refreshMaterialUniforms:r}}function cx(i,e,t,n){let r={},s={},a=[];const o=i.getParameter(i.MAX_UNIFORM_BUFFER_BINDINGS);function l(E,w){const x=w.program;n.uniformBlockBinding(E,x)}function c(E,w){let x=r[E.id];x===void 0&&(_(E),x=h(E),r[E.id]=x,E.addEventListener("dispose",g));const T=w.program;n.updateUBOMapping(E,T);const L=e.render.frame;s[E.id]!==L&&(f(E),s[E.id]=L)}function h(E){const w=u();E.__bindingPointIndex=w;const x=i.createBuffer(),T=E.__size,L=E.usage;return i.bindBuffer(i.UNIFORM_BUFFER,x),i.bufferData(i.UNIFORM_BUFFER,T,L),i.bindBuffer(i.UNIFORM_BUFFER,null),i.bindBufferBase(i.UNIFORM_BUFFER,w,x),x}function u(){for(let E=0;E<o;E++)if(a.indexOf(E)===-1)return a.push(E),E;return console.error("THREE.WebGLRenderer: Maximum number of simultaneously usable uniforms groups reached."),0}function f(E){const w=r[E.id],x=E.uniforms,T=E.__cache;i.bindBuffer(i.UNIFORM_BUFFER,w);for(let L=0,C=x.length;L<C;L++){const R=Array.isArray(x[L])?x[L]:[x[L]];for(let v=0,b=R.length;v<b;v++){const A=R[v];if(p(A,L,v,T)===!0){const U=A.__offset,z=Array.isArray(A.value)?A.value:[A.value];let B=0;for(let V=0;V<z.length;V++){const G=z[V],J=y(G);typeof G=="number"||typeof G=="boolean"?(A.__data[0]=G,i.bufferSubData(i.UNIFORM_BUFFER,U+B,A.__data)):G.isMatrix3?(A.__data[0]=G.elements[0],A.__data[1]=G.elements[1],A.__data[2]=G.elements[2],A.__data[3]=0,A.__data[4]=G.elements[3],A.__data[5]=G.elements[4],A.__data[6]=G.elements[5],A.__data[7]=0,A.__data[8]=G.elements[6],A.__data[9]=G.elements[7],A.__data[10]=G.elements[8],A.__data[11]=0):(G.toArray(A.__data,B),B+=J.storage/Float32Array.BYTES_PER_ELEMENT)}i.bufferSubData(i.UNIFORM_BUFFER,U,A.__data)}}}i.bindBuffer(i.UNIFORM_BUFFER,null)}function p(E,w,x,T){const L=E.value,C=w+"_"+x;if(T[C]===void 0)return typeof L=="number"||typeof L=="boolean"?T[C]=L:T[C]=L.clone(),!0;{const R=T[C];if(typeof L=="number"||typeof L=="boolean"){if(R!==L)return T[C]=L,!0}else if(R.equals(L)===!1)return R.copy(L),!0}return!1}function _(E){const w=E.uniforms;let x=0;const T=16;for(let C=0,R=w.length;C<R;C++){const v=Array.isArray(w[C])?w[C]:[w[C]];for(let b=0,A=v.length;b<A;b++){const U=v[b],z=Array.isArray(U.value)?U.value:[U.value];for(let B=0,V=z.length;B<V;B++){const G=z[B],J=y(G),j=x%T,re=j%J.boundary,le=j+re;x+=re,le!==0&&T-le<J.storage&&(x+=T-le),U.__data=new Float32Array(J.storage/Float32Array.BYTES_PER_ELEMENT),U.__offset=x,x+=J.storage}}}const L=x%T;return L>0&&(x+=T-L),E.__size=x,E.__cache={},this}function y(E){const w={boundary:0,storage:0};return typeof E=="number"||typeof E=="boolean"?(w.boundary=4,w.storage=4):E.isVector2?(w.boundary=8,w.storage=8):E.isVector3||E.isColor?(w.boundary=16,w.storage=12):E.isVector4?(w.boundary=16,w.storage=16):E.isMatrix3?(w.boundary=48,w.storage=48):E.isMatrix4?(w.boundary=64,w.storage=64):E.isTexture?console.warn("THREE.WebGLRenderer: Texture samplers can not be part of an uniforms group."):console.warn("THREE.WebGLRenderer: Unsupported uniform value type.",E),w}function g(E){const w=E.target;w.removeEventListener("dispose",g);const x=a.indexOf(w.__bindingPointIndex);a.splice(x,1),i.deleteBuffer(r[w.id]),delete r[w.id],delete s[w.id]}function m(){for(const E in r)i.deleteBuffer(r[E]);a=[],r={},s={}}return{bind:l,update:c,dispose:m}}class dx{constructor(e={}){const{canvas:t=ap(),context:n=null,depth:r=!0,stencil:s=!1,alpha:a=!1,antialias:o=!1,premultipliedAlpha:l=!0,preserveDrawingBuffer:c=!1,powerPreference:h="default",failIfMajorPerformanceCaveat:u=!1,reversedDepthBuffer:f=!1}=e;this.isWebGLRenderer=!0;let p;if(n!==null){if(typeof WebGLRenderingContext<"u"&&n instanceof WebGLRenderingContext)throw new Error("THREE.WebGLRenderer: WebGL 1 is not supported since r163.");p=n.getContextAttributes().alpha}else p=a;const _=new Uint32Array(4),y=new Int32Array(4);let g=null,m=null;const E=[],w=[];this.domElement=t,this.debug={checkShaderErrors:!0,onShaderError:null},this.autoClear=!0,this.autoClearColor=!0,this.autoClearDepth=!0,this.autoClearStencil=!0,this.sortObjects=!0,this.clippingPlanes=[],this.localClippingEnabled=!1,this.toneMapping=pi,this.toneMappingExposure=1,this.transmissionResolutionScale=1;const x=this;let T=!1;this._outputColorSpace=Et;let L=0,C=0,R=null,v=-1,b=null;const A=new Ye,U=new Ye;let z=null;const B=new Ee(0);let V=0,G=t.width,J=t.height,j=1,re=null,le=null;const Re=new Ye(0,0,G,J),Ne=new Ye(0,0,G,J);let Ze=!1;const it=new Xa;let $=!1,de=!1;const ae=new De,Ue=new P,Fe=new Ye,ke={background:null,fog:null,environment:null,overrideMaterial:null,isScene:!0};let bt=!1;function Qe(){return R===null?j:1}let D=n;function ht(S,F){return t.getContext(S,F)}try{const S={alpha:!0,depth:r,stencil:s,antialias:o,premultipliedAlpha:l,preserveDrawingBuffer:c,powerPreference:h,failIfMajorPerformanceCaveat:u};if("setAttribute"in t&&t.setAttribute("data-engine",`three.js r${Wl}`),t.addEventListener("webglcontextlost",oe,!1),t.addEventListener("webglcontextrestored",me,!1),t.addEventListener("webglcontextcreationerror",ee,!1),D===null){const F="webgl2";if(D=ht(F,S),D===null)throw ht(F)?new Error("Error creating WebGL context with your selected attributes."):new Error("Error creating WebGL context.")}}catch(S){throw console.error("THREE.WebGLRenderer: "+S.message),S}let Ie,nt,Ce,_t,ge,je,Dt,St,I,M,k,K,Q,Y,Te,se,ve,be,ne,fe,Be,Se,ue,Ge;function N(){Ie=new v0(D),Ie.init(),Se=new nx(D,Ie),nt=new f0(D,Ie,e,Se),Ce=new ex(D,Ie),nt.reversedDepthBuffer&&f&&Ce.buffers.depth.setReversed(!0),_t=new S0(D),ge=new Hy,je=new tx(D,Ie,Ce,ge,nt,Se,_t),Dt=new m0(x),St=new x0(x),I=new Cm(D),ue=new u0(D,I),M=new M0(D,I,_t,ue),k=new E0(D,M,I,_t),ne=new w0(D,nt,je),se=new p0(ge),K=new ky(x,Dt,St,Ie,nt,ue,se),Q=new lx(x,ge),Y=new Vy,Te=new Ky(Ie),be=new d0(x,Dt,St,Ce,k,p,l),ve=new Jy(x,k,nt),Ge=new cx(D,_t,nt,Ce),fe=new h0(D,Ie,_t),Be=new b0(D,Ie,_t),_t.programs=K.programs,x.capabilities=nt,x.extensions=Ie,x.properties=ge,x.renderLists=Y,x.shadowMap=ve,x.state=Ce,x.info=_t}N();const ie=new ax(x,D);this.xr=ie,this.getContext=function(){return D},this.getContextAttributes=function(){return D.getContextAttributes()},this.forceContextLoss=function(){const S=Ie.get("WEBGL_lose_context");S&&S.loseContext()},this.forceContextRestore=function(){const S=Ie.get("WEBGL_lose_context");S&&S.restoreContext()},this.getPixelRatio=function(){return j},this.setPixelRatio=function(S){S!==void 0&&(j=S,this.setSize(G,J,!1))},this.getSize=function(S){return S.set(G,J)},this.setSize=function(S,F,W=!0){if(ie.isPresenting){console.warn("THREE.WebGLRenderer: Can't change size while VR device is presenting.");return}G=S,J=F,t.width=Math.floor(S*j),t.height=Math.floor(F*j),W===!0&&(t.style.width=S+"px",t.style.height=F+"px"),this.setViewport(0,0,S,F)},this.getDrawingBufferSize=function(S){return S.set(G*j,J*j).floor()},this.setDrawingBufferSize=function(S,F,W){G=S,J=F,j=W,t.width=Math.floor(S*W),t.height=Math.floor(F*W),this.setViewport(0,0,S,F)},this.getCurrentViewport=function(S){return S.copy(A)},this.getViewport=function(S){return S.copy(Re)},this.setViewport=function(S,F,W,X){S.isVector4?Re.set(S.x,S.y,S.z,S.w):Re.set(S,F,W,X),Ce.viewport(A.copy(Re).multiplyScalar(j).round())},this.getScissor=function(S){return S.copy(Ne)},this.setScissor=function(S,F,W,X){S.isVector4?Ne.set(S.x,S.y,S.z,S.w):Ne.set(S,F,W,X),Ce.scissor(U.copy(Ne).multiplyScalar(j).round())},this.getScissorTest=function(){return Ze},this.setScissorTest=function(S){Ce.setScissorTest(Ze=S)},this.setOpaqueSort=function(S){re=S},this.setTransparentSort=function(S){le=S},this.getClearColor=function(S){return S.copy(be.getClearColor())},this.setClearColor=function(){be.setClearColor(...arguments)},this.getClearAlpha=function(){return be.getClearAlpha()},this.setClearAlpha=function(){be.setClearAlpha(...arguments)},this.clear=function(S=!0,F=!0,W=!0){let X=0;if(S){let O=!1;if(R!==null){const te=R.texture.format;O=te===Jl||te===Zl||te===$l}if(O){const te=R.texture.type,he=te===Sn||te===Di||te===hs||te===fs||te===ql||te===Yl,_e=be.getClearColor(),pe=be.getClearAlpha(),Oe=_e.r,ze=_e.g,Pe=_e.b;he?(_[0]=Oe,_[1]=ze,_[2]=Pe,_[3]=pe,D.clearBufferuiv(D.COLOR,0,_)):(y[0]=Oe,y[1]=ze,y[2]=Pe,y[3]=pe,D.clearBufferiv(D.COLOR,0,y))}else X|=D.COLOR_BUFFER_BIT}F&&(X|=D.DEPTH_BUFFER_BIT),W&&(X|=D.STENCIL_BUFFER_BIT,this.state.buffers.stencil.setMask(4294967295)),D.clear(X)},this.clearColor=function(){this.clear(!0,!1,!1)},this.clearDepth=function(){this.clear(!1,!0,!1)},this.clearStencil=function(){this.clear(!1,!1,!0)},this.dispose=function(){t.removeEventListener("webglcontextlost",oe,!1),t.removeEventListener("webglcontextrestored",me,!1),t.removeEventListener("webglcontextcreationerror",ee,!1),be.dispose(),Y.dispose(),Te.dispose(),ge.dispose(),Dt.dispose(),St.dispose(),k.dispose(),ue.dispose(),Ge.dispose(),K.dispose(),ie.dispose(),ie.removeEventListener("sessionstart",An),ie.removeEventListener("sessionend",Dc),xi.stop()};function oe(S){S.preventDefault(),console.log("THREE.WebGLRenderer: Context Lost."),T=!0}function me(){console.log("THREE.WebGLRenderer: Context Restored."),T=!1;const S=_t.autoReset,F=ve.enabled,W=ve.autoUpdate,X=ve.needsUpdate,O=ve.type;N(),_t.autoReset=S,ve.enabled=F,ve.autoUpdate=W,ve.needsUpdate=X,ve.type=O}function ee(S){console.error("THREE.WebGLRenderer: A WebGL context could not be created. Reason: ",S.statusMessage)}function Z(S){const F=S.target;F.removeEventListener("dispose",Z),ye(F)}function ye(S){He(S),ge.remove(S)}function He(S){const F=ge.get(S).programs;F!==void 0&&(F.forEach(function(W){K.releaseProgram(W)}),S.isShaderMaterial&&K.releaseShaderCache(S))}this.renderBufferDirect=function(S,F,W,X,O,te){F===null&&(F=ke);const he=O.isMesh&&O.matrixWorld.determinant()<0,_e=$h(S,F,W,X,O);Ce.setMaterial(X,he);let pe=W.index,Oe=1;if(X.wireframe===!0){if(pe=M.getWireframeAttribute(W),pe===void 0)return;Oe=2}const ze=W.drawRange,Pe=W.attributes.position;let Ke=ze.start*Oe,ot=(ze.start+ze.count)*Oe;te!==null&&(Ke=Math.max(Ke,te.start*Oe),ot=Math.min(ot,(te.start+te.count)*Oe)),pe!==null?(Ke=Math.max(Ke,0),ot=Math.min(ot,pe.count)):Pe!=null&&(Ke=Math.max(Ke,0),ot=Math.min(ot,Pe.count));const Mt=ot-Ke;if(Mt<0||Mt===1/0)return;ue.setup(O,X,_e,W,pe);let gt,dt=fe;if(pe!==null&&(gt=I.get(pe),dt=Be,dt.setIndex(gt)),O.isMesh)X.wireframe===!0?(Ce.setLineWidth(X.wireframeLinewidth*Qe()),dt.setMode(D.LINES)):dt.setMode(D.TRIANGLES);else if(O.isLine){let Le=X.linewidth;Le===void 0&&(Le=1),Ce.setLineWidth(Le*Qe()),O.isLineSegments?dt.setMode(D.LINES):O.isLineLoop?dt.setMode(D.LINE_LOOP):dt.setMode(D.LINE_STRIP)}else O.isPoints?dt.setMode(D.POINTS):O.isSprite&&dt.setMode(D.TRIANGLES);if(O.isBatchedMesh)if(O._multiDrawInstances!==null)_r("THREE.WebGLRenderer: renderMultiDrawInstances has been deprecated and will be removed in r184. Append to renderMultiDraw arguments and use indirection."),dt.renderMultiDrawInstances(O._multiDrawStarts,O._multiDrawCounts,O._multiDrawCount,O._multiDrawInstances);else if(Ie.get("WEBGL_multi_draw"))dt.renderMultiDraw(O._multiDrawStarts,O._multiDrawCounts,O._multiDrawCount);else{const Le=O._multiDrawStarts,xt=O._multiDrawCounts,tt=O._multiDrawCount,Jt=pe?I.get(pe).bytesPerElement:1,ki=ge.get(X).currentProgram.getUniforms();for(let Qt=0;Qt<tt;Qt++)ki.setValue(D,"_gl_DrawID",Qt),dt.render(Le[Qt]/Jt,xt[Qt])}else if(O.isInstancedMesh)dt.renderInstances(Ke,Mt,O.count);else if(W.isInstancedBufferGeometry){const Le=W._maxInstanceCount!==void 0?W._maxInstanceCount:1/0,xt=Math.min(W.instanceCount,Le);dt.renderInstances(Ke,Mt,xt)}else dt.render(Ke,Mt)};function ft(S,F,W){S.transparent===!0&&S.side===un&&S.forceSinglePass===!1?(S.side=jt,S.needsUpdate=!0,Os(S,F,W),S.side=ei,S.needsUpdate=!0,Os(S,F,W),S.side=un):Os(S,F,W)}this.compile=function(S,F,W=null){W===null&&(W=S),m=Te.get(W),m.init(F),w.push(m),W.traverseVisible(function(O){O.isLight&&O.layers.test(F.layers)&&(m.pushLight(O),O.castShadow&&m.pushShadow(O))}),S!==W&&S.traverseVisible(function(O){O.isLight&&O.layers.test(F.layers)&&(m.pushLight(O),O.castShadow&&m.pushShadow(O))}),m.setupLights();const X=new Set;return S.traverse(function(O){if(!(O.isMesh||O.isPoints||O.isLine||O.isSprite))return;const te=O.material;if(te)if(Array.isArray(te))for(let he=0;he<te.length;he++){const _e=te[he];ft(_e,W,O),X.add(_e)}else ft(te,W,O),X.add(te)}),m=w.pop(),X},this.compileAsync=function(S,F,W=null){const X=this.compile(S,F,W);return new Promise(O=>{function te(){if(X.forEach(function(he){ge.get(he).currentProgram.isReady()&&X.delete(he)}),X.size===0){O(S);return}setTimeout(te,10)}Ie.get("KHR_parallel_shader_compile")!==null?te():setTimeout(te,10)})};let rt=null;function On(S){rt&&rt(S)}function An(){xi.stop()}function Dc(){xi.start()}const xi=new oh;xi.setAnimationLoop(On),typeof self<"u"&&xi.setContext(self),this.setAnimationLoop=function(S){rt=S,ie.setAnimationLoop(S),S===null?xi.stop():xi.start()},ie.addEventListener("sessionstart",An),ie.addEventListener("sessionend",Dc),this.render=function(S,F){if(F!==void 0&&F.isCamera!==!0){console.error("THREE.WebGLRenderer.render: camera is not an instance of THREE.Camera.");return}if(T===!0)return;if(S.matrixWorldAutoUpdate===!0&&S.updateMatrixWorld(),F.parent===null&&F.matrixWorldAutoUpdate===!0&&F.updateMatrixWorld(),ie.enabled===!0&&ie.isPresenting===!0&&(ie.cameraAutoUpdate===!0&&ie.updateCamera(F),F=ie.getCamera()),S.isScene===!0&&S.onBeforeRender(x,S,F,R),m=Te.get(S,w.length),m.init(F),w.push(m),ae.multiplyMatrices(F.projectionMatrix,F.matrixWorldInverse),it.setFromProjectionMatrix(ae,Ln,F.reversedDepth),de=this.localClippingEnabled,$=se.init(this.clippingPlanes,de),g=Y.get(S,E.length),g.init(),E.push(g),ie.enabled===!0&&ie.isPresenting===!0){const te=x.xr.getDepthSensingMesh();te!==null&&eo(te,F,-1/0,x.sortObjects)}eo(S,F,0,x.sortObjects),g.finish(),x.sortObjects===!0&&g.sort(re,le),bt=ie.enabled===!1||ie.isPresenting===!1||ie.hasDepthSensing()===!1,bt&&be.addToRenderList(g,S),this.info.render.frame++,$===!0&&se.beginShadows();const W=m.state.shadowsArray;ve.render(W,S,F),$===!0&&se.endShadows(),this.info.autoReset===!0&&this.info.reset();const X=g.opaque,O=g.transmissive;if(m.setupLights(),F.isArrayCamera){const te=F.cameras;if(O.length>0)for(let he=0,_e=te.length;he<_e;he++){const pe=te[he];Uc(X,O,S,pe)}bt&&be.render(S);for(let he=0,_e=te.length;he<_e;he++){const pe=te[he];Nc(g,S,pe,pe.viewport)}}else O.length>0&&Uc(X,O,S,F),bt&&be.render(S),Nc(g,S,F);R!==null&&C===0&&(je.updateMultisampleRenderTarget(R),je.updateRenderTargetMipmap(R)),S.isScene===!0&&S.onAfterRender(x,S,F),ue.resetDefaultState(),v=-1,b=null,w.pop(),w.length>0?(m=w[w.length-1],$===!0&&se.setGlobalState(x.clippingPlanes,m.state.camera)):m=null,E.pop(),E.length>0?g=E[E.length-1]:g=null};function eo(S,F,W,X){if(S.visible===!1)return;if(S.layers.test(F.layers)){if(S.isGroup)W=S.renderOrder;else if(S.isLOD)S.autoUpdate===!0&&S.update(F);else if(S.isLight)m.pushLight(S),S.castShadow&&m.pushShadow(S);else if(S.isSprite){if(!S.frustumCulled||it.intersectsSprite(S)){X&&Fe.setFromMatrixPosition(S.matrixWorld).applyMatrix4(ae);const he=k.update(S),_e=S.material;_e.visible&&g.push(S,he,_e,W,Fe.z,null)}}else if((S.isMesh||S.isLine||S.isPoints)&&(!S.frustumCulled||it.intersectsObject(S))){const he=k.update(S),_e=S.material;if(X&&(S.boundingSphere!==void 0?(S.boundingSphere===null&&S.computeBoundingSphere(),Fe.copy(S.boundingSphere.center)):(he.boundingSphere===null&&he.computeBoundingSphere(),Fe.copy(he.boundingSphere.center)),Fe.applyMatrix4(S.matrixWorld).applyMatrix4(ae)),Array.isArray(_e)){const pe=he.groups;for(let Oe=0,ze=pe.length;Oe<ze;Oe++){const Pe=pe[Oe],Ke=_e[Pe.materialIndex];Ke&&Ke.visible&&g.push(S,he,Ke,W,Fe.z,Pe)}}else _e.visible&&g.push(S,he,_e,W,Fe.z,null)}}const te=S.children;for(let he=0,_e=te.length;he<_e;he++)eo(te[he],F,W,X)}function Nc(S,F,W,X){const O=S.opaque,te=S.transmissive,he=S.transparent;m.setupLightsView(W),$===!0&&se.setGlobalState(x.clippingPlanes,W),X&&Ce.viewport(A.copy(X)),O.length>0&&Fs(O,F,W),te.length>0&&Fs(te,F,W),he.length>0&&Fs(he,F,W),Ce.buffers.depth.setTest(!0),Ce.buffers.depth.setMask(!0),Ce.buffers.color.setMask(!0),Ce.setPolygonOffset(!1)}function Uc(S,F,W,X){if((W.isScene===!0?W.overrideMaterial:null)!==null)return;m.state.transmissionRenderTarget[X.id]===void 0&&(m.state.transmissionRenderTarget[X.id]=new Ni(1,1,{generateMipmaps:!0,type:Ie.has("EXT_color_buffer_half_float")||Ie.has("EXT_color_buffer_float")?In:Sn,minFilter:Pn,samples:4,stencilBuffer:s,resolveDepthBuffer:!1,resolveStencilBuffer:!1,colorSpace:Je.workingColorSpace}));const te=m.state.transmissionRenderTarget[X.id],he=X.viewport||A;te.setSize(he.z*x.transmissionResolutionScale,he.w*x.transmissionResolutionScale);const _e=x.getRenderTarget(),pe=x.getActiveCubeFace(),Oe=x.getActiveMipmapLevel();x.setRenderTarget(te),x.getClearColor(B),V=x.getClearAlpha(),V<1&&x.setClearColor(16777215,.5),x.clear(),bt&&be.render(W);const ze=x.toneMapping;x.toneMapping=pi;const Pe=X.viewport;if(X.viewport!==void 0&&(X.viewport=void 0),m.setupLightsView(X),$===!0&&se.setGlobalState(x.clippingPlanes,X),Fs(S,W,X),je.updateMultisampleRenderTarget(te),je.updateRenderTargetMipmap(te),Ie.has("WEBGL_multisampled_render_to_texture")===!1){let Ke=!1;for(let ot=0,Mt=F.length;ot<Mt;ot++){const gt=F[ot],dt=gt.object,Le=gt.geometry,xt=gt.material,tt=gt.group;if(xt.side===un&&dt.layers.test(X.layers)){const Jt=xt.side;xt.side=jt,xt.needsUpdate=!0,Fc(dt,W,X,Le,xt,tt),xt.side=Jt,xt.needsUpdate=!0,Ke=!0}}Ke===!0&&(je.updateMultisampleRenderTarget(te),je.updateRenderTargetMipmap(te))}x.setRenderTarget(_e,pe,Oe),x.setClearColor(B,V),Pe!==void 0&&(X.viewport=Pe),x.toneMapping=ze}function Fs(S,F,W){const X=F.isScene===!0?F.overrideMaterial:null;for(let O=0,te=S.length;O<te;O++){const he=S[O],_e=he.object,pe=he.geometry,Oe=he.group;let ze=he.material;ze.allowOverride===!0&&X!==null&&(ze=X),_e.layers.test(W.layers)&&Fc(_e,F,W,pe,ze,Oe)}}function Fc(S,F,W,X,O,te){S.onBeforeRender(x,F,W,X,O,te),S.modelViewMatrix.multiplyMatrices(W.matrixWorldInverse,S.matrixWorld),S.normalMatrix.getNormalMatrix(S.modelViewMatrix),O.onBeforeRender(x,F,W,X,S,te),O.transparent===!0&&O.side===un&&O.forceSinglePass===!1?(O.side=jt,O.needsUpdate=!0,x.renderBufferDirect(W,F,X,O,S,te),O.side=ei,O.needsUpdate=!0,x.renderBufferDirect(W,F,X,O,S,te),O.side=un):x.renderBufferDirect(W,F,X,O,S,te),S.onAfterRender(x,F,W,X,O,te)}function Os(S,F,W){F.isScene!==!0&&(F=ke);const X=ge.get(S),O=m.state.lights,te=m.state.shadowsArray,he=O.state.version,_e=K.getParameters(S,O.state,te,F,W),pe=K.getProgramCacheKey(_e);let Oe=X.programs;X.environment=S.isMeshStandardMaterial?F.environment:null,X.fog=F.fog,X.envMap=(S.isMeshStandardMaterial?St:Dt).get(S.envMap||X.environment),X.envMapRotation=X.environment!==null&&S.envMap===null?F.environmentRotation:S.envMapRotation,Oe===void 0&&(S.addEventListener("dispose",Z),Oe=new Map,X.programs=Oe);let ze=Oe.get(pe);if(ze!==void 0){if(X.currentProgram===ze&&X.lightsStateVersion===he)return Bc(S,_e),ze}else _e.uniforms=K.getUniforms(S),S.onBeforeCompile(_e,x),ze=K.acquireProgram(_e,pe),Oe.set(pe,ze),X.uniforms=_e.uniforms;const Pe=X.uniforms;return(!S.isShaderMaterial&&!S.isRawShaderMaterial||S.clipping===!0)&&(Pe.clippingPlanes=se.uniform),Bc(S,_e),X.needsLights=Jh(S),X.lightsStateVersion=he,X.needsLights&&(Pe.ambientLightColor.value=O.state.ambient,Pe.lightProbe.value=O.state.probe,Pe.directionalLights.value=O.state.directional,Pe.directionalLightShadows.value=O.state.directionalShadow,Pe.spotLights.value=O.state.spot,Pe.spotLightShadows.value=O.state.spotShadow,Pe.rectAreaLights.value=O.state.rectArea,Pe.ltc_1.value=O.state.rectAreaLTC1,Pe.ltc_2.value=O.state.rectAreaLTC2,Pe.pointLights.value=O.state.point,Pe.pointLightShadows.value=O.state.pointShadow,Pe.hemisphereLights.value=O.state.hemi,Pe.directionalShadowMap.value=O.state.directionalShadowMap,Pe.directionalShadowMatrix.value=O.state.directionalShadowMatrix,Pe.spotShadowMap.value=O.state.spotShadowMap,Pe.spotLightMatrix.value=O.state.spotLightMatrix,Pe.spotLightMap.value=O.state.spotLightMap,Pe.pointShadowMap.value=O.state.pointShadowMap,Pe.pointShadowMatrix.value=O.state.pointShadowMatrix),X.currentProgram=ze,X.uniformsList=null,ze}function Oc(S){if(S.uniformsList===null){const F=S.currentProgram.getUniforms();S.uniformsList=Ea.seqWithValue(F.seq,S.uniforms)}return S.uniformsList}function Bc(S,F){const W=ge.get(S);W.outputColorSpace=F.outputColorSpace,W.batching=F.batching,W.batchingColor=F.batchingColor,W.instancing=F.instancing,W.instancingColor=F.instancingColor,W.instancingMorph=F.instancingMorph,W.skinning=F.skinning,W.morphTargets=F.morphTargets,W.morphNormals=F.morphNormals,W.morphColors=F.morphColors,W.morphTargetsCount=F.morphTargetsCount,W.numClippingPlanes=F.numClippingPlanes,W.numIntersection=F.numClipIntersection,W.vertexAlphas=F.vertexAlphas,W.vertexTangents=F.vertexTangents,W.toneMapping=F.toneMapping}function $h(S,F,W,X,O){F.isScene!==!0&&(F=ke),je.resetTextureUnits();const te=F.fog,he=X.isMeshStandardMaterial?F.environment:null,_e=R===null?x.outputColorSpace:R.isXRRenderTarget===!0?R.texture.colorSpace:zt,pe=(X.isMeshStandardMaterial?St:Dt).get(X.envMap||he),Oe=X.vertexColors===!0&&!!W.attributes.color&&W.attributes.color.itemSize===4,ze=!!W.attributes.tangent&&(!!X.normalMap||X.anisotropy>0),Pe=!!W.morphAttributes.position,Ke=!!W.morphAttributes.normal,ot=!!W.morphAttributes.color;let Mt=pi;X.toneMapped&&(R===null||R.isXRRenderTarget===!0)&&(Mt=x.toneMapping);const gt=W.morphAttributes.position||W.morphAttributes.normal||W.morphAttributes.color,dt=gt!==void 0?gt.length:0,Le=ge.get(X),xt=m.state.lights;if($===!0&&(de===!0||S!==b)){const Ht=S===b&&X.id===v;se.setState(X,S,Ht)}let tt=!1;X.version===Le.__version?(Le.needsLights&&Le.lightsStateVersion!==xt.state.version||Le.outputColorSpace!==_e||O.isBatchedMesh&&Le.batching===!1||!O.isBatchedMesh&&Le.batching===!0||O.isBatchedMesh&&Le.batchingColor===!0&&O.colorTexture===null||O.isBatchedMesh&&Le.batchingColor===!1&&O.colorTexture!==null||O.isInstancedMesh&&Le.instancing===!1||!O.isInstancedMesh&&Le.instancing===!0||O.isSkinnedMesh&&Le.skinning===!1||!O.isSkinnedMesh&&Le.skinning===!0||O.isInstancedMesh&&Le.instancingColor===!0&&O.instanceColor===null||O.isInstancedMesh&&Le.instancingColor===!1&&O.instanceColor!==null||O.isInstancedMesh&&Le.instancingMorph===!0&&O.morphTexture===null||O.isInstancedMesh&&Le.instancingMorph===!1&&O.morphTexture!==null||Le.envMap!==pe||X.fog===!0&&Le.fog!==te||Le.numClippingPlanes!==void 0&&(Le.numClippingPlanes!==se.numPlanes||Le.numIntersection!==se.numIntersection)||Le.vertexAlphas!==Oe||Le.vertexTangents!==ze||Le.morphTargets!==Pe||Le.morphNormals!==Ke||Le.morphColors!==ot||Le.toneMapping!==Mt||Le.morphTargetsCount!==dt)&&(tt=!0):(tt=!0,Le.__version=X.version);let Jt=Le.currentProgram;tt===!0&&(Jt=Os(X,F,O));let ki=!1,Qt=!1,Gr=!1;const vt=Jt.getUniforms(),an=Le.uniforms;if(Ce.useProgram(Jt.program)&&(ki=!0,Qt=!0,Gr=!0),X.id!==v&&(v=X.id,Qt=!0),ki||b!==S){Ce.buffers.depth.getReversed()&&S.reversedDepth!==!0&&(S._reversedDepth=!0,S.updateProjectionMatrix()),vt.setValue(D,"projectionMatrix",S.projectionMatrix),vt.setValue(D,"viewMatrix",S.matrixWorldInverse);const Yt=vt.map.cameraPosition;Yt!==void 0&&Yt.setValue(D,Ue.setFromMatrixPosition(S.matrixWorld)),nt.logarithmicDepthBuffer&&vt.setValue(D,"logDepthBufFC",2/(Math.log(S.far+1)/Math.LN2)),(X.isMeshPhongMaterial||X.isMeshToonMaterial||X.isMeshLambertMaterial||X.isMeshBasicMaterial||X.isMeshStandardMaterial||X.isShaderMaterial)&&vt.setValue(D,"isOrthographic",S.isOrthographicCamera===!0),b!==S&&(b=S,Qt=!0,Gr=!0)}if(O.isSkinnedMesh){vt.setOptional(D,O,"bindMatrix"),vt.setOptional(D,O,"bindMatrixInverse");const Ht=O.skeleton;Ht&&(Ht.boneTexture===null&&Ht.computeBoneTexture(),vt.setValue(D,"boneTexture",Ht.boneTexture,je))}O.isBatchedMesh&&(vt.setOptional(D,O,"batchingTexture"),vt.setValue(D,"batchingTexture",O._matricesTexture,je),vt.setOptional(D,O,"batchingIdTexture"),vt.setValue(D,"batchingIdTexture",O._indirectTexture,je),vt.setOptional(D,O,"batchingColorTexture"),O._colorsTexture!==null&&vt.setValue(D,"batchingColorTexture",O._colorsTexture,je));const on=W.morphAttributes;if((on.position!==void 0||on.normal!==void 0||on.color!==void 0)&&ne.update(O,W,Jt),(Qt||Le.receiveShadow!==O.receiveShadow)&&(Le.receiveShadow=O.receiveShadow,vt.setValue(D,"receiveShadow",O.receiveShadow)),X.isMeshGouraudMaterial&&X.envMap!==null&&(an.envMap.value=pe,an.flipEnvMap.value=pe.isCubeTexture&&pe.isRenderTargetTexture===!1?-1:1),X.isMeshStandardMaterial&&X.envMap===null&&F.environment!==null&&(an.envMapIntensity.value=F.environmentIntensity),Qt&&(vt.setValue(D,"toneMappingExposure",x.toneMappingExposure),Le.needsLights&&Zh(an,Gr),te&&X.fog===!0&&Q.refreshFogUniforms(an,te),Q.refreshMaterialUniforms(an,X,j,J,m.state.transmissionRenderTarget[S.id]),Ea.upload(D,Oc(Le),an,je)),X.isShaderMaterial&&X.uniformsNeedUpdate===!0&&(Ea.upload(D,Oc(Le),an,je),X.uniformsNeedUpdate=!1),X.isSpriteMaterial&&vt.setValue(D,"center",O.center),vt.setValue(D,"modelViewMatrix",O.modelViewMatrix),vt.setValue(D,"normalMatrix",O.normalMatrix),vt.setValue(D,"modelMatrix",O.matrixWorld),X.isShaderMaterial||X.isRawShaderMaterial){const Ht=X.uniformsGroups;for(let Yt=0,to=Ht.length;Yt<to;Yt++){const vi=Ht[Yt];Ge.update(vi,Jt),Ge.bind(vi,Jt)}}return Jt}function Zh(S,F){S.ambientLightColor.needsUpdate=F,S.lightProbe.needsUpdate=F,S.directionalLights.needsUpdate=F,S.directionalLightShadows.needsUpdate=F,S.pointLights.needsUpdate=F,S.pointLightShadows.needsUpdate=F,S.spotLights.needsUpdate=F,S.spotLightShadows.needsUpdate=F,S.rectAreaLights.needsUpdate=F,S.hemisphereLights.needsUpdate=F}function Jh(S){return S.isMeshLambertMaterial||S.isMeshToonMaterial||S.isMeshPhongMaterial||S.isMeshStandardMaterial||S.isShadowMaterial||S.isShaderMaterial&&S.lights===!0}this.getActiveCubeFace=function(){return L},this.getActiveMipmapLevel=function(){return C},this.getRenderTarget=function(){return R},this.setRenderTargetTextures=function(S,F,W){const X=ge.get(S);X.__autoAllocateDepthBuffer=S.resolveDepthBuffer===!1,X.__autoAllocateDepthBuffer===!1&&(X.__useRenderToTexture=!1),ge.get(S.texture).__webglTexture=F,ge.get(S.depthTexture).__webglTexture=X.__autoAllocateDepthBuffer?void 0:W,X.__hasExternalTextures=!0},this.setRenderTargetFramebuffer=function(S,F){const W=ge.get(S);W.__webglFramebuffer=F,W.__useDefaultFramebuffer=F===void 0};const Qh=D.createFramebuffer();this.setRenderTarget=function(S,F=0,W=0){R=S,L=F,C=W;let X=!0,O=null,te=!1,he=!1;if(S){const pe=ge.get(S);if(pe.__useDefaultFramebuffer!==void 0)Ce.bindFramebuffer(D.FRAMEBUFFER,null),X=!1;else if(pe.__webglFramebuffer===void 0)je.setupRenderTarget(S);else if(pe.__hasExternalTextures)je.rebindTextures(S,ge.get(S.texture).__webglTexture,ge.get(S.depthTexture).__webglTexture);else if(S.depthBuffer){const Pe=S.depthTexture;if(pe.__boundDepthTexture!==Pe){if(Pe!==null&&ge.has(Pe)&&(S.width!==Pe.image.width||S.height!==Pe.image.height))throw new Error("WebGLRenderTarget: Attached DepthTexture is initialized to the incorrect size.");je.setupDepthRenderbuffer(S)}}const Oe=S.texture;(Oe.isData3DTexture||Oe.isDataArrayTexture||Oe.isCompressedArrayTexture)&&(he=!0);const ze=ge.get(S).__webglFramebuffer;S.isWebGLCubeRenderTarget?(Array.isArray(ze[F])?O=ze[F][W]:O=ze[F],te=!0):S.samples>0&&je.useMultisampledRTT(S)===!1?O=ge.get(S).__webglMultisampledFramebuffer:Array.isArray(ze)?O=ze[W]:O=ze,A.copy(S.viewport),U.copy(S.scissor),z=S.scissorTest}else A.copy(Re).multiplyScalar(j).floor(),U.copy(Ne).multiplyScalar(j).floor(),z=Ze;if(W!==0&&(O=Qh),Ce.bindFramebuffer(D.FRAMEBUFFER,O)&&X&&Ce.drawBuffers(S,O),Ce.viewport(A),Ce.scissor(U),Ce.setScissorTest(z),te){const pe=ge.get(S.texture);D.framebufferTexture2D(D.FRAMEBUFFER,D.COLOR_ATTACHMENT0,D.TEXTURE_CUBE_MAP_POSITIVE_X+F,pe.__webglTexture,W)}else if(he){const pe=F;for(let Oe=0;Oe<S.textures.length;Oe++){const ze=ge.get(S.textures[Oe]);D.framebufferTextureLayer(D.FRAMEBUFFER,D.COLOR_ATTACHMENT0+Oe,ze.__webglTexture,W,pe)}}else if(S!==null&&W!==0){const pe=ge.get(S.texture);D.framebufferTexture2D(D.FRAMEBUFFER,D.COLOR_ATTACHMENT0,D.TEXTURE_2D,pe.__webglTexture,W)}v=-1},this.readRenderTargetPixels=function(S,F,W,X,O,te,he,_e=0){if(!(S&&S.isWebGLRenderTarget)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");return}let pe=ge.get(S).__webglFramebuffer;if(S.isWebGLCubeRenderTarget&&he!==void 0&&(pe=pe[he]),pe){Ce.bindFramebuffer(D.FRAMEBUFFER,pe);try{const Oe=S.textures[_e],ze=Oe.format,Pe=Oe.type;if(!nt.textureFormatReadable(ze)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not in RGBA or implementation defined format.");return}if(!nt.textureTypeReadable(Pe)){console.error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not in UnsignedByteType or implementation defined type.");return}F>=0&&F<=S.width-X&&W>=0&&W<=S.height-O&&(S.textures.length>1&&D.readBuffer(D.COLOR_ATTACHMENT0+_e),D.readPixels(F,W,X,O,Se.convert(ze),Se.convert(Pe),te))}finally{const Oe=R!==null?ge.get(R).__webglFramebuffer:null;Ce.bindFramebuffer(D.FRAMEBUFFER,Oe)}}},this.readRenderTargetPixelsAsync=async function(S,F,W,X,O,te,he,_e=0){if(!(S&&S.isWebGLRenderTarget))throw new Error("THREE.WebGLRenderer.readRenderTargetPixels: renderTarget is not THREE.WebGLRenderTarget.");let pe=ge.get(S).__webglFramebuffer;if(S.isWebGLCubeRenderTarget&&he!==void 0&&(pe=pe[he]),pe)if(F>=0&&F<=S.width-X&&W>=0&&W<=S.height-O){Ce.bindFramebuffer(D.FRAMEBUFFER,pe);const Oe=S.textures[_e],ze=Oe.format,Pe=Oe.type;if(!nt.textureFormatReadable(ze))throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in RGBA or implementation defined format.");if(!nt.textureTypeReadable(Pe))throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: renderTarget is not in UnsignedByteType or implementation defined type.");const Ke=D.createBuffer();D.bindBuffer(D.PIXEL_PACK_BUFFER,Ke),D.bufferData(D.PIXEL_PACK_BUFFER,te.byteLength,D.STREAM_READ),S.textures.length>1&&D.readBuffer(D.COLOR_ATTACHMENT0+_e),D.readPixels(F,W,X,O,Se.convert(ze),Se.convert(Pe),0);const ot=R!==null?ge.get(R).__webglFramebuffer:null;Ce.bindFramebuffer(D.FRAMEBUFFER,ot);const Mt=D.fenceSync(D.SYNC_GPU_COMMANDS_COMPLETE,0);return D.flush(),await op(D,Mt,4),D.bindBuffer(D.PIXEL_PACK_BUFFER,Ke),D.getBufferSubData(D.PIXEL_PACK_BUFFER,0,te),D.deleteBuffer(Ke),D.deleteSync(Mt),te}else throw new Error("THREE.WebGLRenderer.readRenderTargetPixelsAsync: requested read bounds are out of range.")},this.copyFramebufferToTexture=function(S,F=null,W=0){const X=Math.pow(2,-W),O=Math.floor(S.image.width*X),te=Math.floor(S.image.height*X),he=F!==null?F.x:0,_e=F!==null?F.y:0;je.setTexture2D(S,0),D.copyTexSubImage2D(D.TEXTURE_2D,W,0,0,he,_e,O,te),Ce.unbindTexture()};const ef=D.createFramebuffer(),tf=D.createFramebuffer();this.copyTextureToTexture=function(S,F,W=null,X=null,O=0,te=null){te===null&&(O!==0?(_r("WebGLRenderer: copyTextureToTexture function signature has changed to support src and dst mipmap levels."),te=O,O=0):te=0);let he,_e,pe,Oe,ze,Pe,Ke,ot,Mt;const gt=S.isCompressedTexture?S.mipmaps[te]:S.image;if(W!==null)he=W.max.x-W.min.x,_e=W.max.y-W.min.y,pe=W.isBox3?W.max.z-W.min.z:1,Oe=W.min.x,ze=W.min.y,Pe=W.isBox3?W.min.z:0;else{const on=Math.pow(2,-O);he=Math.floor(gt.width*on),_e=Math.floor(gt.height*on),S.isDataArrayTexture?pe=gt.depth:S.isData3DTexture?pe=Math.floor(gt.depth*on):pe=1,Oe=0,ze=0,Pe=0}X!==null?(Ke=X.x,ot=X.y,Mt=X.z):(Ke=0,ot=0,Mt=0);const dt=Se.convert(F.format),Le=Se.convert(F.type);let xt;F.isData3DTexture?(je.setTexture3D(F,0),xt=D.TEXTURE_3D):F.isDataArrayTexture||F.isCompressedArrayTexture?(je.setTexture2DArray(F,0),xt=D.TEXTURE_2D_ARRAY):(je.setTexture2D(F,0),xt=D.TEXTURE_2D),D.pixelStorei(D.UNPACK_FLIP_Y_WEBGL,F.flipY),D.pixelStorei(D.UNPACK_PREMULTIPLY_ALPHA_WEBGL,F.premultiplyAlpha),D.pixelStorei(D.UNPACK_ALIGNMENT,F.unpackAlignment);const tt=D.getParameter(D.UNPACK_ROW_LENGTH),Jt=D.getParameter(D.UNPACK_IMAGE_HEIGHT),ki=D.getParameter(D.UNPACK_SKIP_PIXELS),Qt=D.getParameter(D.UNPACK_SKIP_ROWS),Gr=D.getParameter(D.UNPACK_SKIP_IMAGES);D.pixelStorei(D.UNPACK_ROW_LENGTH,gt.width),D.pixelStorei(D.UNPACK_IMAGE_HEIGHT,gt.height),D.pixelStorei(D.UNPACK_SKIP_PIXELS,Oe),D.pixelStorei(D.UNPACK_SKIP_ROWS,ze),D.pixelStorei(D.UNPACK_SKIP_IMAGES,Pe);const vt=S.isDataArrayTexture||S.isData3DTexture,an=F.isDataArrayTexture||F.isData3DTexture;if(S.isDepthTexture){const on=ge.get(S),Ht=ge.get(F),Yt=ge.get(on.__renderTarget),to=ge.get(Ht.__renderTarget);Ce.bindFramebuffer(D.READ_FRAMEBUFFER,Yt.__webglFramebuffer),Ce.bindFramebuffer(D.DRAW_FRAMEBUFFER,to.__webglFramebuffer);for(let vi=0;vi<pe;vi++)vt&&(D.framebufferTextureLayer(D.READ_FRAMEBUFFER,D.COLOR_ATTACHMENT0,ge.get(S).__webglTexture,O,Pe+vi),D.framebufferTextureLayer(D.DRAW_FRAMEBUFFER,D.COLOR_ATTACHMENT0,ge.get(F).__webglTexture,te,Mt+vi)),D.blitFramebuffer(Oe,ze,he,_e,Ke,ot,he,_e,D.DEPTH_BUFFER_BIT,D.NEAREST);Ce.bindFramebuffer(D.READ_FRAMEBUFFER,null),Ce.bindFramebuffer(D.DRAW_FRAMEBUFFER,null)}else if(O!==0||S.isRenderTargetTexture||ge.has(S)){const on=ge.get(S),Ht=ge.get(F);Ce.bindFramebuffer(D.READ_FRAMEBUFFER,ef),Ce.bindFramebuffer(D.DRAW_FRAMEBUFFER,tf);for(let Yt=0;Yt<pe;Yt++)vt?D.framebufferTextureLayer(D.READ_FRAMEBUFFER,D.COLOR_ATTACHMENT0,on.__webglTexture,O,Pe+Yt):D.framebufferTexture2D(D.READ_FRAMEBUFFER,D.COLOR_ATTACHMENT0,D.TEXTURE_2D,on.__webglTexture,O),an?D.framebufferTextureLayer(D.DRAW_FRAMEBUFFER,D.COLOR_ATTACHMENT0,Ht.__webglTexture,te,Mt+Yt):D.framebufferTexture2D(D.DRAW_FRAMEBUFFER,D.COLOR_ATTACHMENT0,D.TEXTURE_2D,Ht.__webglTexture,te),O!==0?D.blitFramebuffer(Oe,ze,he,_e,Ke,ot,he,_e,D.COLOR_BUFFER_BIT,D.NEAREST):an?D.copyTexSubImage3D(xt,te,Ke,ot,Mt+Yt,Oe,ze,he,_e):D.copyTexSubImage2D(xt,te,Ke,ot,Oe,ze,he,_e);Ce.bindFramebuffer(D.READ_FRAMEBUFFER,null),Ce.bindFramebuffer(D.DRAW_FRAMEBUFFER,null)}else an?S.isDataTexture||S.isData3DTexture?D.texSubImage3D(xt,te,Ke,ot,Mt,he,_e,pe,dt,Le,gt.data):F.isCompressedArrayTexture?D.compressedTexSubImage3D(xt,te,Ke,ot,Mt,he,_e,pe,dt,gt.data):D.texSubImage3D(xt,te,Ke,ot,Mt,he,_e,pe,dt,Le,gt):S.isDataTexture?D.texSubImage2D(D.TEXTURE_2D,te,Ke,ot,he,_e,dt,Le,gt.data):S.isCompressedTexture?D.compressedTexSubImage2D(D.TEXTURE_2D,te,Ke,ot,gt.width,gt.height,dt,gt.data):D.texSubImage2D(D.TEXTURE_2D,te,Ke,ot,he,_e,dt,Le,gt);D.pixelStorei(D.UNPACK_ROW_LENGTH,tt),D.pixelStorei(D.UNPACK_IMAGE_HEIGHT,Jt),D.pixelStorei(D.UNPACK_SKIP_PIXELS,ki),D.pixelStorei(D.UNPACK_SKIP_ROWS,Qt),D.pixelStorei(D.UNPACK_SKIP_IMAGES,Gr),te===0&&F.generateMipmaps&&D.generateMipmap(xt),Ce.unbindTexture()},this.copyTextureToTexture3D=function(S,F,W=null,X=null,O=0){return _r('WebGLRenderer: copyTextureToTexture3D function has been deprecated. Use "copyTextureToTexture" instead.'),this.copyTextureToTexture(S,F,W,X,O)},this.initRenderTarget=function(S){ge.get(S).__webglFramebuffer===void 0&&je.setupRenderTarget(S)},this.initTexture=function(S){S.isCubeTexture?je.setTextureCube(S,0):S.isData3DTexture?je.setTexture3D(S,0):S.isDataArrayTexture||S.isCompressedArrayTexture?je.setTexture2DArray(S,0):je.setTexture2D(S,0),Ce.unbindTexture()},this.resetState=function(){L=0,C=0,R=null,Ce.reset(),ue.reset()},typeof __THREE_DEVTOOLS__<"u"&&__THREE_DEVTOOLS__.dispatchEvent(new CustomEvent("observe",{detail:this}))}get coordinateSystem(){return Ln}get outputColorSpace(){return this._outputColorSpace}set outputColorSpace(e){this._outputColorSpace=e;const t=this.getContext();t.drawingBufferColorSpace=Je._getDrawingBufferColorSpace(e),t.unpackColorSpace=Je._getUnpackColorSpace()}}const au={type:"change"},mc={type:"start"},fh={type:"end"},_a=new Fr,ou=new jn,ux=Math.cos(70*wn.DEG2RAD),Rt=new P,Kt=2*Math.PI,ct={NONE:-1,ROTATE:0,DOLLY:1,PAN:2,TOUCH_ROTATE:3,TOUCH_PAN:4,TOUCH_DOLLY_PAN:5,TOUCH_DOLLY_ROTATE:6},ko=1e-6;class hx extends Am{constructor(e,t=null){super(e,t),this.state=ct.NONE,this.target=new P,this.cursor=new P,this.minDistance=0,this.maxDistance=1/0,this.minZoom=0,this.maxZoom=1/0,this.minTargetRadius=0,this.maxTargetRadius=1/0,this.minPolarAngle=0,this.maxPolarAngle=Math.PI,this.minAzimuthAngle=-1/0,this.maxAzimuthAngle=1/0,this.enableDamping=!1,this.dampingFactor=.05,this.enableZoom=!0,this.zoomSpeed=1,this.enableRotate=!0,this.rotateSpeed=1,this.keyRotateSpeed=1,this.enablePan=!0,this.panSpeed=1,this.screenSpacePanning=!0,this.keyPanSpeed=7,this.zoomToCursor=!1,this.autoRotate=!1,this.autoRotateSpeed=2,this.keys={LEFT:"ArrowLeft",UP:"ArrowUp",RIGHT:"ArrowRight",BOTTOM:"ArrowDown"},this.mouseButtons={LEFT:pr.ROTATE,MIDDLE:pr.DOLLY,RIGHT:pr.PAN},this.touches={ONE:dr.ROTATE,TWO:dr.DOLLY_PAN},this.target0=this.target.clone(),this.position0=this.object.position.clone(),this.zoom0=this.object.zoom,this._domElementKeyEvents=null,this._lastPosition=new P,this._lastQuaternion=new En,this._lastTargetPosition=new P,this._quat=new En().setFromUnitVectors(e.up,new P(0,1,0)),this._quatInverse=this._quat.clone().invert(),this._spherical=new Ud,this._sphericalDelta=new Ud,this._scale=1,this._panOffset=new P,this._rotateStart=new xe,this._rotateEnd=new xe,this._rotateDelta=new xe,this._panStart=new xe,this._panEnd=new xe,this._panDelta=new xe,this._dollyStart=new xe,this._dollyEnd=new xe,this._dollyDelta=new xe,this._dollyDirection=new P,this._mouse=new xe,this._performCursorZoom=!1,this._pointers=[],this._pointerPositions={},this._controlActive=!1,this._onPointerMove=px.bind(this),this._onPointerDown=fx.bind(this),this._onPointerUp=mx.bind(this),this._onContextMenu=bx.bind(this),this._onMouseWheel=yx.bind(this),this._onKeyDown=xx.bind(this),this._onTouchStart=vx.bind(this),this._onTouchMove=Mx.bind(this),this._onMouseDown=gx.bind(this),this._onMouseMove=_x.bind(this),this._interceptControlDown=Sx.bind(this),this._interceptControlUp=wx.bind(this),this.domElement!==null&&this.connect(this.domElement),this.update()}connect(e){super.connect(e),this.domElement.addEventListener("pointerdown",this._onPointerDown),this.domElement.addEventListener("pointercancel",this._onPointerUp),this.domElement.addEventListener("contextmenu",this._onContextMenu),this.domElement.addEventListener("wheel",this._onMouseWheel,{passive:!1}),this.domElement.getRootNode().addEventListener("keydown",this._interceptControlDown,{passive:!0,capture:!0}),this.domElement.style.touchAction="none"}disconnect(){this.domElement.removeEventListener("pointerdown",this._onPointerDown),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.domElement.removeEventListener("pointercancel",this._onPointerUp),this.domElement.removeEventListener("wheel",this._onMouseWheel),this.domElement.removeEventListener("contextmenu",this._onContextMenu),this.stopListenToKeyEvents(),this.domElement.getRootNode().removeEventListener("keydown",this._interceptControlDown,{capture:!0}),this.domElement.style.touchAction="auto"}dispose(){this.disconnect()}getPolarAngle(){return this._spherical.phi}getAzimuthalAngle(){return this._spherical.theta}getDistance(){return this.object.position.distanceTo(this.target)}listenToKeyEvents(e){e.addEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=e}stopListenToKeyEvents(){this._domElementKeyEvents!==null&&(this._domElementKeyEvents.removeEventListener("keydown",this._onKeyDown),this._domElementKeyEvents=null)}saveState(){this.target0.copy(this.target),this.position0.copy(this.object.position),this.zoom0=this.object.zoom}reset(){this.target.copy(this.target0),this.object.position.copy(this.position0),this.object.zoom=this.zoom0,this.object.updateProjectionMatrix(),this.dispatchEvent(au),this.update(),this.state=ct.NONE}update(e=null){const t=this.object.position;Rt.copy(t).sub(this.target),Rt.applyQuaternion(this._quat),this._spherical.setFromVector3(Rt),this.autoRotate&&this.state===ct.NONE&&this._rotateLeft(this._getAutoRotationAngle(e)),this.enableDamping?(this._spherical.theta+=this._sphericalDelta.theta*this.dampingFactor,this._spherical.phi+=this._sphericalDelta.phi*this.dampingFactor):(this._spherical.theta+=this._sphericalDelta.theta,this._spherical.phi+=this._sphericalDelta.phi);let n=this.minAzimuthAngle,r=this.maxAzimuthAngle;isFinite(n)&&isFinite(r)&&(n<-Math.PI?n+=Kt:n>Math.PI&&(n-=Kt),r<-Math.PI?r+=Kt:r>Math.PI&&(r-=Kt),n<=r?this._spherical.theta=Math.max(n,Math.min(r,this._spherical.theta)):this._spherical.theta=this._spherical.theta>(n+r)/2?Math.max(n,this._spherical.theta):Math.min(r,this._spherical.theta)),this._spherical.phi=Math.max(this.minPolarAngle,Math.min(this.maxPolarAngle,this._spherical.phi)),this._spherical.makeSafe(),this.enableDamping===!0?this.target.addScaledVector(this._panOffset,this.dampingFactor):this.target.add(this._panOffset),this.target.sub(this.cursor),this.target.clampLength(this.minTargetRadius,this.maxTargetRadius),this.target.add(this.cursor);let s=!1;if(this.zoomToCursor&&this._performCursorZoom||this.object.isOrthographicCamera)this._spherical.radius=this._clampDistance(this._spherical.radius);else{const a=this._spherical.radius;this._spherical.radius=this._clampDistance(this._spherical.radius*this._scale),s=a!=this._spherical.radius}if(Rt.setFromSpherical(this._spherical),Rt.applyQuaternion(this._quatInverse),t.copy(this.target).add(Rt),this.object.lookAt(this.target),this.enableDamping===!0?(this._sphericalDelta.theta*=1-this.dampingFactor,this._sphericalDelta.phi*=1-this.dampingFactor,this._panOffset.multiplyScalar(1-this.dampingFactor)):(this._sphericalDelta.set(0,0,0),this._panOffset.set(0,0,0)),this.zoomToCursor&&this._performCursorZoom){let a=null;if(this.object.isPerspectiveCamera){const o=Rt.length();a=this._clampDistance(o*this._scale);const l=o-a;this.object.position.addScaledVector(this._dollyDirection,l),this.object.updateMatrixWorld(),s=!!l}else if(this.object.isOrthographicCamera){const o=new P(this._mouse.x,this._mouse.y,0);o.unproject(this.object);const l=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),this.object.updateProjectionMatrix(),s=l!==this.object.zoom;const c=new P(this._mouse.x,this._mouse.y,0);c.unproject(this.object),this.object.position.sub(c).add(o),this.object.updateMatrixWorld(),a=Rt.length()}else console.warn("WARNING: OrbitControls.js encountered an unknown camera type - zoom to cursor disabled."),this.zoomToCursor=!1;a!==null&&(this.screenSpacePanning?this.target.set(0,0,-1).transformDirection(this.object.matrix).multiplyScalar(a).add(this.object.position):(_a.origin.copy(this.object.position),_a.direction.set(0,0,-1).transformDirection(this.object.matrix),Math.abs(this.object.up.dot(_a.direction))<ux?this.object.lookAt(this.target):(ou.setFromNormalAndCoplanarPoint(this.object.up,this.target),_a.intersectPlane(ou,this.target))))}else if(this.object.isOrthographicCamera){const a=this.object.zoom;this.object.zoom=Math.max(this.minZoom,Math.min(this.maxZoom,this.object.zoom/this._scale)),a!==this.object.zoom&&(this.object.updateProjectionMatrix(),s=!0)}return this._scale=1,this._performCursorZoom=!1,s||this._lastPosition.distanceToSquared(this.object.position)>ko||8*(1-this._lastQuaternion.dot(this.object.quaternion))>ko||this._lastTargetPosition.distanceToSquared(this.target)>ko?(this.dispatchEvent(au),this._lastPosition.copy(this.object.position),this._lastQuaternion.copy(this.object.quaternion),this._lastTargetPosition.copy(this.target),!0):!1}_getAutoRotationAngle(e){return e!==null?Kt/60*this.autoRotateSpeed*e:Kt/60/60*this.autoRotateSpeed}_getZoomScale(e){const t=Math.abs(e*.01);return Math.pow(.95,this.zoomSpeed*t)}_rotateLeft(e){this._sphericalDelta.theta-=e}_rotateUp(e){this._sphericalDelta.phi-=e}_panLeft(e,t){Rt.setFromMatrixColumn(t,0),Rt.multiplyScalar(-e),this._panOffset.add(Rt)}_panUp(e,t){this.screenSpacePanning===!0?Rt.setFromMatrixColumn(t,1):(Rt.setFromMatrixColumn(t,0),Rt.crossVectors(this.object.up,Rt)),Rt.multiplyScalar(e),this._panOffset.add(Rt)}_pan(e,t){const n=this.domElement;if(this.object.isPerspectiveCamera){const r=this.object.position;Rt.copy(r).sub(this.target);let s=Rt.length();s*=Math.tan(this.object.fov/2*Math.PI/180),this._panLeft(2*e*s/n.clientHeight,this.object.matrix),this._panUp(2*t*s/n.clientHeight,this.object.matrix)}else this.object.isOrthographicCamera?(this._panLeft(e*(this.object.right-this.object.left)/this.object.zoom/n.clientWidth,this.object.matrix),this._panUp(t*(this.object.top-this.object.bottom)/this.object.zoom/n.clientHeight,this.object.matrix)):(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - pan disabled."),this.enablePan=!1)}_dollyOut(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale/=e:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_dollyIn(e){this.object.isPerspectiveCamera||this.object.isOrthographicCamera?this._scale*=e:(console.warn("WARNING: OrbitControls.js encountered an unknown camera type - dolly/zoom disabled."),this.enableZoom=!1)}_updateZoomParameters(e,t){if(!this.zoomToCursor)return;this._performCursorZoom=!0;const n=this.domElement.getBoundingClientRect(),r=e-n.left,s=t-n.top,a=n.width,o=n.height;this._mouse.x=r/a*2-1,this._mouse.y=-(s/o)*2+1,this._dollyDirection.set(this._mouse.x,this._mouse.y,1).unproject(this.object).sub(this.object.position).normalize()}_clampDistance(e){return Math.max(this.minDistance,Math.min(this.maxDistance,e))}_handleMouseDownRotate(e){this._rotateStart.set(e.clientX,e.clientY)}_handleMouseDownDolly(e){this._updateZoomParameters(e.clientX,e.clientX),this._dollyStart.set(e.clientX,e.clientY)}_handleMouseDownPan(e){this._panStart.set(e.clientX,e.clientY)}_handleMouseMoveRotate(e){this._rotateEnd.set(e.clientX,e.clientY),this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);const t=this.domElement;this._rotateLeft(Kt*this._rotateDelta.x/t.clientHeight),this._rotateUp(Kt*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd),this.update()}_handleMouseMoveDolly(e){this._dollyEnd.set(e.clientX,e.clientY),this._dollyDelta.subVectors(this._dollyEnd,this._dollyStart),this._dollyDelta.y>0?this._dollyOut(this._getZoomScale(this._dollyDelta.y)):this._dollyDelta.y<0&&this._dollyIn(this._getZoomScale(this._dollyDelta.y)),this._dollyStart.copy(this._dollyEnd),this.update()}_handleMouseMovePan(e){this._panEnd.set(e.clientX,e.clientY),this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd),this.update()}_handleMouseWheel(e){this._updateZoomParameters(e.clientX,e.clientY),e.deltaY<0?this._dollyIn(this._getZoomScale(e.deltaY)):e.deltaY>0&&this._dollyOut(this._getZoomScale(e.deltaY)),this.update()}_handleKeyDown(e){let t=!1;switch(e.code){case this.keys.UP:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateUp(Kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,this.keyPanSpeed),t=!0;break;case this.keys.BOTTOM:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateUp(-Kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(0,-this.keyPanSpeed),t=!0;break;case this.keys.LEFT:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateLeft(Kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(this.keyPanSpeed,0),t=!0;break;case this.keys.RIGHT:e.ctrlKey||e.metaKey||e.shiftKey?this.enableRotate&&this._rotateLeft(-Kt*this.keyRotateSpeed/this.domElement.clientHeight):this.enablePan&&this._pan(-this.keyPanSpeed,0),t=!0;break}t&&(e.preventDefault(),this.update())}_handleTouchStartRotate(e){if(this._pointers.length===1)this._rotateStart.set(e.pageX,e.pageY);else{const t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._rotateStart.set(n,r)}}_handleTouchStartPan(e){if(this._pointers.length===1)this._panStart.set(e.pageX,e.pageY);else{const t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._panStart.set(n,r)}}_handleTouchStartDolly(e){const t=this._getSecondPointerPosition(e),n=e.pageX-t.x,r=e.pageY-t.y,s=Math.sqrt(n*n+r*r);this._dollyStart.set(0,s)}_handleTouchStartDollyPan(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enablePan&&this._handleTouchStartPan(e)}_handleTouchStartDollyRotate(e){this.enableZoom&&this._handleTouchStartDolly(e),this.enableRotate&&this._handleTouchStartRotate(e)}_handleTouchMoveRotate(e){if(this._pointers.length==1)this._rotateEnd.set(e.pageX,e.pageY);else{const n=this._getSecondPointerPosition(e),r=.5*(e.pageX+n.x),s=.5*(e.pageY+n.y);this._rotateEnd.set(r,s)}this._rotateDelta.subVectors(this._rotateEnd,this._rotateStart).multiplyScalar(this.rotateSpeed);const t=this.domElement;this._rotateLeft(Kt*this._rotateDelta.x/t.clientHeight),this._rotateUp(Kt*this._rotateDelta.y/t.clientHeight),this._rotateStart.copy(this._rotateEnd)}_handleTouchMovePan(e){if(this._pointers.length===1)this._panEnd.set(e.pageX,e.pageY);else{const t=this._getSecondPointerPosition(e),n=.5*(e.pageX+t.x),r=.5*(e.pageY+t.y);this._panEnd.set(n,r)}this._panDelta.subVectors(this._panEnd,this._panStart).multiplyScalar(this.panSpeed),this._pan(this._panDelta.x,this._panDelta.y),this._panStart.copy(this._panEnd)}_handleTouchMoveDolly(e){const t=this._getSecondPointerPosition(e),n=e.pageX-t.x,r=e.pageY-t.y,s=Math.sqrt(n*n+r*r);this._dollyEnd.set(0,s),this._dollyDelta.set(0,Math.pow(this._dollyEnd.y/this._dollyStart.y,this.zoomSpeed)),this._dollyOut(this._dollyDelta.y),this._dollyStart.copy(this._dollyEnd);const a=(e.pageX+t.x)*.5,o=(e.pageY+t.y)*.5;this._updateZoomParameters(a,o)}_handleTouchMoveDollyPan(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enablePan&&this._handleTouchMovePan(e)}_handleTouchMoveDollyRotate(e){this.enableZoom&&this._handleTouchMoveDolly(e),this.enableRotate&&this._handleTouchMoveRotate(e)}_addPointer(e){this._pointers.push(e.pointerId)}_removePointer(e){delete this._pointerPositions[e.pointerId];for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId){this._pointers.splice(t,1);return}}_isTrackingPointer(e){for(let t=0;t<this._pointers.length;t++)if(this._pointers[t]==e.pointerId)return!0;return!1}_trackPointer(e){let t=this._pointerPositions[e.pointerId];t===void 0&&(t=new xe,this._pointerPositions[e.pointerId]=t),t.set(e.pageX,e.pageY)}_getSecondPointerPosition(e){const t=e.pointerId===this._pointers[0]?this._pointers[1]:this._pointers[0];return this._pointerPositions[t]}_customWheelEvent(e){const t=e.deltaMode,n={clientX:e.clientX,clientY:e.clientY,deltaY:e.deltaY};switch(t){case 1:n.deltaY*=16;break;case 2:n.deltaY*=100;break}return e.ctrlKey&&!this._controlActive&&(n.deltaY*=10),n}}function fx(i){this.enabled!==!1&&(this._pointers.length===0&&(this.domElement.setPointerCapture(i.pointerId),this.domElement.addEventListener("pointermove",this._onPointerMove),this.domElement.addEventListener("pointerup",this._onPointerUp)),!this._isTrackingPointer(i)&&(this._addPointer(i),i.pointerType==="touch"?this._onTouchStart(i):this._onMouseDown(i)))}function px(i){this.enabled!==!1&&(i.pointerType==="touch"?this._onTouchMove(i):this._onMouseMove(i))}function mx(i){switch(this._removePointer(i),this._pointers.length){case 0:this.domElement.releasePointerCapture(i.pointerId),this.domElement.removeEventListener("pointermove",this._onPointerMove),this.domElement.removeEventListener("pointerup",this._onPointerUp),this.dispatchEvent(fh),this.state=ct.NONE;break;case 1:const e=this._pointers[0],t=this._pointerPositions[e];this._onTouchStart({pointerId:e,pageX:t.x,pageY:t.y});break}}function gx(i){let e;switch(i.button){case 0:e=this.mouseButtons.LEFT;break;case 1:e=this.mouseButtons.MIDDLE;break;case 2:e=this.mouseButtons.RIGHT;break;default:e=-1}switch(e){case pr.DOLLY:if(this.enableZoom===!1)return;this._handleMouseDownDolly(i),this.state=ct.DOLLY;break;case pr.ROTATE:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=ct.PAN}else{if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=ct.ROTATE}break;case pr.PAN:if(i.ctrlKey||i.metaKey||i.shiftKey){if(this.enableRotate===!1)return;this._handleMouseDownRotate(i),this.state=ct.ROTATE}else{if(this.enablePan===!1)return;this._handleMouseDownPan(i),this.state=ct.PAN}break;default:this.state=ct.NONE}this.state!==ct.NONE&&this.dispatchEvent(mc)}function _x(i){switch(this.state){case ct.ROTATE:if(this.enableRotate===!1)return;this._handleMouseMoveRotate(i);break;case ct.DOLLY:if(this.enableZoom===!1)return;this._handleMouseMoveDolly(i);break;case ct.PAN:if(this.enablePan===!1)return;this._handleMouseMovePan(i);break}}function yx(i){this.enabled===!1||this.enableZoom===!1||this.state!==ct.NONE||(i.preventDefault(),this.dispatchEvent(mc),this._handleMouseWheel(this._customWheelEvent(i)),this.dispatchEvent(fh))}function xx(i){this.enabled!==!1&&this._handleKeyDown(i)}function vx(i){switch(this._trackPointer(i),this._pointers.length){case 1:switch(this.touches.ONE){case dr.ROTATE:if(this.enableRotate===!1)return;this._handleTouchStartRotate(i),this.state=ct.TOUCH_ROTATE;break;case dr.PAN:if(this.enablePan===!1)return;this._handleTouchStartPan(i),this.state=ct.TOUCH_PAN;break;default:this.state=ct.NONE}break;case 2:switch(this.touches.TWO){case dr.DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchStartDollyPan(i),this.state=ct.TOUCH_DOLLY_PAN;break;case dr.DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchStartDollyRotate(i),this.state=ct.TOUCH_DOLLY_ROTATE;break;default:this.state=ct.NONE}break;default:this.state=ct.NONE}this.state!==ct.NONE&&this.dispatchEvent(mc)}function Mx(i){switch(this._trackPointer(i),this.state){case ct.TOUCH_ROTATE:if(this.enableRotate===!1)return;this._handleTouchMoveRotate(i),this.update();break;case ct.TOUCH_PAN:if(this.enablePan===!1)return;this._handleTouchMovePan(i),this.update();break;case ct.TOUCH_DOLLY_PAN:if(this.enableZoom===!1&&this.enablePan===!1)return;this._handleTouchMoveDollyPan(i),this.update();break;case ct.TOUCH_DOLLY_ROTATE:if(this.enableZoom===!1&&this.enableRotate===!1)return;this._handleTouchMoveDollyRotate(i),this.update();break;default:this.state=ct.NONE}}function bx(i){this.enabled!==!1&&i.preventDefault()}function Sx(i){i.key==="Control"&&(this._controlActive=!0,this.domElement.getRootNode().addEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function wx(i){i.key==="Control"&&(this._controlActive=!1,this.domElement.getRootNode().removeEventListener("keyup",this._interceptControlUp,{passive:!0,capture:!0}))}function lu(i,e){if(e===Df)return console.warn("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Geometry already defined as triangles."),i;if(e===Rl||e===Ou){let t=i.getIndex();if(t===null){const a=[],o=i.getAttribute("position");if(o!==void 0){for(let l=0;l<o.count;l++)a.push(l);i.setIndex(a),t=i.getIndex()}else return console.error("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Undefined position attribute. Processing not possible."),i}const n=t.count-2,r=[];if(e===Rl)for(let a=1;a<=n;a++)r.push(t.getX(0)),r.push(t.getX(a)),r.push(t.getX(a+1));else for(let a=0;a<n;a++)a%2===0?(r.push(t.getX(a)),r.push(t.getX(a+1)),r.push(t.getX(a+2))):(r.push(t.getX(a+2)),r.push(t.getX(a+1)),r.push(t.getX(a)));r.length/3!==n&&console.error("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Unable to generate correct amount of triangles.");const s=i.clone();return s.setIndex(r),s.clearGroups(),s}else return console.error("THREE.BufferGeometryUtils.toTrianglesDrawMode(): Unknown draw mode:",e),i}class ph extends Bi{constructor(e){super(e),this.dracoLoader=null,this.ktx2Loader=null,this.meshoptDecoder=null,this.pluginCallbacks=[],this.register(function(t){return new Cx(t)}),this.register(function(t){return new Px(t)}),this.register(function(t){return new zx(t)}),this.register(function(t){return new kx(t)}),this.register(function(t){return new Hx(t)}),this.register(function(t){return new Lx(t)}),this.register(function(t){return new Dx(t)}),this.register(function(t){return new Nx(t)}),this.register(function(t){return new Ux(t)}),this.register(function(t){return new Rx(t)}),this.register(function(t){return new Fx(t)}),this.register(function(t){return new Ix(t)}),this.register(function(t){return new Bx(t)}),this.register(function(t){return new Ox(t)}),this.register(function(t){return new Tx(t)}),this.register(function(t){return new Gx(t)}),this.register(function(t){return new Vx(t)})}load(e,t,n,r){const s=this;let a;if(this.resourcePath!=="")a=this.resourcePath;else if(this.path!==""){const c=cs.extractUrlBase(e);a=cs.resolveURL(c,this.path)}else a=cs.extractUrlBase(e);this.manager.itemStart(e);const o=function(c){r?r(c):console.error(c),s.manager.itemError(e),s.manager.itemEnd(e)},l=new cc(this.manager);l.setPath(this.path),l.setResponseType("arraybuffer"),l.setRequestHeader(this.requestHeader),l.setWithCredentials(this.withCredentials),l.load(e,function(c){try{s.parse(c,a,function(h){t(h),s.manager.itemEnd(e)},o)}catch(h){o(h)}},n,o)}setDRACOLoader(e){return this.dracoLoader=e,this}setKTX2Loader(e){return this.ktx2Loader=e,this}setMeshoptDecoder(e){return this.meshoptDecoder=e,this}register(e){return this.pluginCallbacks.indexOf(e)===-1&&this.pluginCallbacks.push(e),this}unregister(e){return this.pluginCallbacks.indexOf(e)!==-1&&this.pluginCallbacks.splice(this.pluginCallbacks.indexOf(e),1),this}parse(e,t,n,r){let s;const a={},o={},l=new TextDecoder;if(typeof e=="string")s=JSON.parse(e);else if(e instanceof ArrayBuffer)if(l.decode(new Uint8Array(e,0,4))===mh){try{a[qe.KHR_BINARY_GLTF]=new Wx(e)}catch(u){r&&r(u);return}s=JSON.parse(a[qe.KHR_BINARY_GLTF].content)}else s=JSON.parse(l.decode(e));else s=e;if(s.asset===void 0||s.asset.version[0]<2){r&&r(new Error("THREE.GLTFLoader: Unsupported asset. glTF versions >=2.0 are supported."));return}const c=new iv(s,{path:t||this.resourcePath||"",crossOrigin:this.crossOrigin,requestHeader:this.requestHeader,manager:this.manager,ktx2Loader:this.ktx2Loader,meshoptDecoder:this.meshoptDecoder});c.fileLoader.setRequestHeader(this.requestHeader);for(let h=0;h<this.pluginCallbacks.length;h++){const u=this.pluginCallbacks[h](c);u.name||console.error("THREE.GLTFLoader: Invalid plugin found: missing name"),o[u.name]=u,a[u.name]=!0}if(s.extensionsUsed)for(let h=0;h<s.extensionsUsed.length;++h){const u=s.extensionsUsed[h],f=s.extensionsRequired||[];switch(u){case qe.KHR_MATERIALS_UNLIT:a[u]=new Ax;break;case qe.KHR_DRACO_MESH_COMPRESSION:a[u]=new Xx(s,this.dracoLoader);break;case qe.KHR_TEXTURE_TRANSFORM:a[u]=new jx;break;case qe.KHR_MESH_QUANTIZATION:a[u]=new qx;break;default:f.indexOf(u)>=0&&o[u]===void 0&&console.warn('THREE.GLTFLoader: Unknown extension "'+u+'".')}}c.setExtensions(a),c.setPlugins(o),c.parse(n,r)}parseAsync(e,t){const n=this;return new Promise(function(r,s){n.parse(e,t,r,s)})}}function Ex(){let i={};return{get:function(e){return i[e]},add:function(e,t){i[e]=t},remove:function(e){delete i[e]},removeAll:function(){i={}}}}const qe={KHR_BINARY_GLTF:"KHR_binary_glTF",KHR_DRACO_MESH_COMPRESSION:"KHR_draco_mesh_compression",KHR_LIGHTS_PUNCTUAL:"KHR_lights_punctual",KHR_MATERIALS_CLEARCOAT:"KHR_materials_clearcoat",KHR_MATERIALS_DISPERSION:"KHR_materials_dispersion",KHR_MATERIALS_IOR:"KHR_materials_ior",KHR_MATERIALS_SHEEN:"KHR_materials_sheen",KHR_MATERIALS_SPECULAR:"KHR_materials_specular",KHR_MATERIALS_TRANSMISSION:"KHR_materials_transmission",KHR_MATERIALS_IRIDESCENCE:"KHR_materials_iridescence",KHR_MATERIALS_ANISOTROPY:"KHR_materials_anisotropy",KHR_MATERIALS_UNLIT:"KHR_materials_unlit",KHR_MATERIALS_VOLUME:"KHR_materials_volume",KHR_TEXTURE_BASISU:"KHR_texture_basisu",KHR_TEXTURE_TRANSFORM:"KHR_texture_transform",KHR_MESH_QUANTIZATION:"KHR_mesh_quantization",KHR_MATERIALS_EMISSIVE_STRENGTH:"KHR_materials_emissive_strength",EXT_MATERIALS_BUMP:"EXT_materials_bump",EXT_TEXTURE_WEBP:"EXT_texture_webp",EXT_TEXTURE_AVIF:"EXT_texture_avif",EXT_MESHOPT_COMPRESSION:"EXT_meshopt_compression",EXT_MESH_GPU_INSTANCING:"EXT_mesh_gpu_instancing"};class Tx{constructor(e){this.parser=e,this.name=qe.KHR_LIGHTS_PUNCTUAL,this.cache={refs:{},uses:{}}}_markDefs(){const e=this.parser,t=this.parser.json.nodes||[];for(let n=0,r=t.length;n<r;n++){const s=t[n];s.extensions&&s.extensions[this.name]&&s.extensions[this.name].light!==void 0&&e._addNodeRef(this.cache,s.extensions[this.name].light)}}_loadLight(e){const t=this.parser,n="light:"+e;let r=t.cache.get(n);if(r)return r;const s=t.json,l=((s.extensions&&s.extensions[this.name]||{}).lights||[])[e];let c;const h=new Ee(16777215);l.color!==void 0&&h.setRGB(l.color[0],l.color[1],l.color[2],zt);const u=l.range!==void 0?l.range:0;switch(l.type){case"directional":c=new sh(h),c.target.position.set(0,0,-1),c.add(c.target);break;case"point":c=new rh(h),c.distance=u;break;case"spot":c=new um(h),c.distance=u,l.spot=l.spot||{},l.spot.innerConeAngle=l.spot.innerConeAngle!==void 0?l.spot.innerConeAngle:0,l.spot.outerConeAngle=l.spot.outerConeAngle!==void 0?l.spot.outerConeAngle:Math.PI/4,c.angle=l.spot.outerConeAngle,c.penumbra=1-l.spot.innerConeAngle/l.spot.outerConeAngle,c.target.position.set(0,0,-1),c.add(c.target);break;default:throw new Error("THREE.GLTFLoader: Unexpected light type: "+l.type)}return c.position.set(0,0,0),Xn(c,l),l.intensity!==void 0&&(c.intensity=l.intensity),c.name=t.createUniqueName(l.name||"light_"+e),r=Promise.resolve(c),t.cache.add(n,r),r}getDependency(e,t){if(e==="light")return this._loadLight(t)}createNodeAttachment(e){const t=this,n=this.parser,s=n.json.nodes[e],o=(s.extensions&&s.extensions[this.name]||{}).light;return o===void 0?null:this._loadLight(o).then(function(l){return n._getNodeRef(t.cache,o,l)})}}class Ax{constructor(){this.name=qe.KHR_MATERIALS_UNLIT}getMaterialType(){return Kn}extendParams(e,t,n){const r=[];e.color=new Ee(1,1,1),e.opacity=1;const s=t.pbrMetallicRoughness;if(s){if(Array.isArray(s.baseColorFactor)){const a=s.baseColorFactor;e.color.setRGB(a[0],a[1],a[2],zt),e.opacity=a[3]}s.baseColorTexture!==void 0&&r.push(n.assignTexture(e,"map",s.baseColorTexture,Et))}return Promise.all(r)}}class Rx{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_EMISSIVE_STRENGTH}extendMaterialParams(e,t){const r=this.parser.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=r.extensions[this.name].emissiveStrength;return s!==void 0&&(t.emissiveIntensity=s),Promise.resolve()}}class Cx{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_CLEARCOAT}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[],a=r.extensions[this.name];if(a.clearcoatFactor!==void 0&&(t.clearcoat=a.clearcoatFactor),a.clearcoatTexture!==void 0&&s.push(n.assignTexture(t,"clearcoatMap",a.clearcoatTexture)),a.clearcoatRoughnessFactor!==void 0&&(t.clearcoatRoughness=a.clearcoatRoughnessFactor),a.clearcoatRoughnessTexture!==void 0&&s.push(n.assignTexture(t,"clearcoatRoughnessMap",a.clearcoatRoughnessTexture)),a.clearcoatNormalTexture!==void 0&&(s.push(n.assignTexture(t,"clearcoatNormalMap",a.clearcoatNormalTexture)),a.clearcoatNormalTexture.scale!==void 0)){const o=a.clearcoatNormalTexture.scale;t.clearcoatNormalScale=new xe(o,o)}return Promise.all(s)}}class Px{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_DISPERSION}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const r=this.parser.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=r.extensions[this.name];return t.dispersion=s.dispersion!==void 0?s.dispersion:0,Promise.resolve()}}class Ix{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_IRIDESCENCE}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[],a=r.extensions[this.name];return a.iridescenceFactor!==void 0&&(t.iridescence=a.iridescenceFactor),a.iridescenceTexture!==void 0&&s.push(n.assignTexture(t,"iridescenceMap",a.iridescenceTexture)),a.iridescenceIor!==void 0&&(t.iridescenceIOR=a.iridescenceIor),t.iridescenceThicknessRange===void 0&&(t.iridescenceThicknessRange=[100,400]),a.iridescenceThicknessMinimum!==void 0&&(t.iridescenceThicknessRange[0]=a.iridescenceThicknessMinimum),a.iridescenceThicknessMaximum!==void 0&&(t.iridescenceThicknessRange[1]=a.iridescenceThicknessMaximum),a.iridescenceThicknessTexture!==void 0&&s.push(n.assignTexture(t,"iridescenceThicknessMap",a.iridescenceThicknessTexture)),Promise.all(s)}}class Lx{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_SHEEN}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[];t.sheenColor=new Ee(0,0,0),t.sheenRoughness=0,t.sheen=1;const a=r.extensions[this.name];if(a.sheenColorFactor!==void 0){const o=a.sheenColorFactor;t.sheenColor.setRGB(o[0],o[1],o[2],zt)}return a.sheenRoughnessFactor!==void 0&&(t.sheenRoughness=a.sheenRoughnessFactor),a.sheenColorTexture!==void 0&&s.push(n.assignTexture(t,"sheenColorMap",a.sheenColorTexture,Et)),a.sheenRoughnessTexture!==void 0&&s.push(n.assignTexture(t,"sheenRoughnessMap",a.sheenRoughnessTexture)),Promise.all(s)}}class Dx{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_TRANSMISSION}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[],a=r.extensions[this.name];return a.transmissionFactor!==void 0&&(t.transmission=a.transmissionFactor),a.transmissionTexture!==void 0&&s.push(n.assignTexture(t,"transmissionMap",a.transmissionTexture)),Promise.all(s)}}class Nx{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_VOLUME}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[],a=r.extensions[this.name];t.thickness=a.thicknessFactor!==void 0?a.thicknessFactor:0,a.thicknessTexture!==void 0&&s.push(n.assignTexture(t,"thicknessMap",a.thicknessTexture)),t.attenuationDistance=a.attenuationDistance||1/0;const o=a.attenuationColor||[1,1,1];return t.attenuationColor=new Ee().setRGB(o[0],o[1],o[2],zt),Promise.all(s)}}class Ux{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_IOR}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const r=this.parser.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=r.extensions[this.name];return t.ior=s.ior!==void 0?s.ior:1.5,Promise.resolve()}}class Fx{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_SPECULAR}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[],a=r.extensions[this.name];t.specularIntensity=a.specularFactor!==void 0?a.specularFactor:1,a.specularTexture!==void 0&&s.push(n.assignTexture(t,"specularIntensityMap",a.specularTexture));const o=a.specularColorFactor||[1,1,1];return t.specularColor=new Ee().setRGB(o[0],o[1],o[2],zt),a.specularColorTexture!==void 0&&s.push(n.assignTexture(t,"specularColorMap",a.specularColorTexture,Et)),Promise.all(s)}}class Ox{constructor(e){this.parser=e,this.name=qe.EXT_MATERIALS_BUMP}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[],a=r.extensions[this.name];return t.bumpScale=a.bumpFactor!==void 0?a.bumpFactor:1,a.bumpTexture!==void 0&&s.push(n.assignTexture(t,"bumpMap",a.bumpTexture)),Promise.all(s)}}class Bx{constructor(e){this.parser=e,this.name=qe.KHR_MATERIALS_ANISOTROPY}getMaterialType(e){const n=this.parser.json.materials[e];return!n.extensions||!n.extensions[this.name]?null:mn}extendMaterialParams(e,t){const n=this.parser,r=n.json.materials[e];if(!r.extensions||!r.extensions[this.name])return Promise.resolve();const s=[],a=r.extensions[this.name];return a.anisotropyStrength!==void 0&&(t.anisotropy=a.anisotropyStrength),a.anisotropyRotation!==void 0&&(t.anisotropyRotation=a.anisotropyRotation),a.anisotropyTexture!==void 0&&s.push(n.assignTexture(t,"anisotropyMap",a.anisotropyTexture)),Promise.all(s)}}class zx{constructor(e){this.parser=e,this.name=qe.KHR_TEXTURE_BASISU}loadTexture(e){const t=this.parser,n=t.json,r=n.textures[e];if(!r.extensions||!r.extensions[this.name])return null;const s=r.extensions[this.name],a=t.options.ktx2Loader;if(!a){if(n.extensionsRequired&&n.extensionsRequired.indexOf(this.name)>=0)throw new Error("THREE.GLTFLoader: setKTX2Loader must be called before loading KTX2 textures");return null}return t.loadTextureImage(e,s.source,a)}}class kx{constructor(e){this.parser=e,this.name=qe.EXT_TEXTURE_WEBP}loadTexture(e){const t=this.name,n=this.parser,r=n.json,s=r.textures[e];if(!s.extensions||!s.extensions[t])return null;const a=s.extensions[t],o=r.images[a.source];let l=n.textureLoader;if(o.uri){const c=n.options.manager.getHandler(o.uri);c!==null&&(l=c)}return n.loadTextureImage(e,a.source,l)}}class Hx{constructor(e){this.parser=e,this.name=qe.EXT_TEXTURE_AVIF}loadTexture(e){const t=this.name,n=this.parser,r=n.json,s=r.textures[e];if(!s.extensions||!s.extensions[t])return null;const a=s.extensions[t],o=r.images[a.source];let l=n.textureLoader;if(o.uri){const c=n.options.manager.getHandler(o.uri);c!==null&&(l=c)}return n.loadTextureImage(e,a.source,l)}}class Gx{constructor(e){this.name=qe.EXT_MESHOPT_COMPRESSION,this.parser=e}loadBufferView(e){const t=this.parser.json,n=t.bufferViews[e];if(n.extensions&&n.extensions[this.name]){const r=n.extensions[this.name],s=this.parser.getDependency("buffer",r.buffer),a=this.parser.options.meshoptDecoder;if(!a||!a.supported){if(t.extensionsRequired&&t.extensionsRequired.indexOf(this.name)>=0)throw new Error("THREE.GLTFLoader: setMeshoptDecoder must be called before loading compressed files");return null}return s.then(function(o){const l=r.byteOffset||0,c=r.byteLength||0,h=r.count,u=r.byteStride,f=new Uint8Array(o,l,c);return a.decodeGltfBufferAsync?a.decodeGltfBufferAsync(h,u,f,r.mode,r.filter).then(function(p){return p.buffer}):a.ready.then(function(){const p=new ArrayBuffer(h*u);return a.decodeGltfBuffer(new Uint8Array(p),h,u,f,r.mode,r.filter),p})})}else return null}}class Vx{constructor(e){this.name=qe.EXT_MESH_GPU_INSTANCING,this.parser=e}createNodeMesh(e){const t=this.parser.json,n=t.nodes[e];if(!n.extensions||!n.extensions[this.name]||n.mesh===void 0)return null;const r=t.meshes[n.mesh];for(const c of r.primitives)if(c.mode!==cn.TRIANGLES&&c.mode!==cn.TRIANGLE_STRIP&&c.mode!==cn.TRIANGLE_FAN&&c.mode!==void 0)return null;const a=n.extensions[this.name].attributes,o=[],l={};for(const c in a)o.push(this.parser.getDependency("accessor",a[c]).then(h=>(l[c]=h,l[c])));return o.length<1?null:(o.push(this.parser.createNodeMesh(e)),Promise.all(o).then(c=>{const h=c.pop(),u=h.isGroup?h.children:[h],f=c[0].count,p=[];for(const _ of u){const y=new De,g=new P,m=new En,E=new P(1,1,1),w=new bs(_.geometry,_.material,f);for(let x=0;x<f;x++)l.TRANSLATION&&g.fromBufferAttribute(l.TRANSLATION,x),l.ROTATION&&m.fromBufferAttribute(l.ROTATION,x),l.SCALE&&E.fromBufferAttribute(l.SCALE,x),w.setMatrixAt(x,y.compose(g,m,E));for(const x in l)if(x==="_COLOR_0"){const T=l[x];w.instanceColor=new Pl(T.array,T.itemSize,T.normalized)}else x!=="TRANSLATION"&&x!=="ROTATION"&&x!=="SCALE"&&_.geometry.setAttribute(x,l[x]);pt.prototype.copy.call(w,_),this.parser.assignFinalMaterial(w),p.push(w)}return h.isGroup?(h.clear(),h.add(...p),h):p[0]}))}}const mh="glTF",es=12,cu={JSON:1313821514,BIN:5130562};class Wx{constructor(e){this.name=qe.KHR_BINARY_GLTF,this.content=null,this.body=null;const t=new DataView(e,0,es),n=new TextDecoder;if(this.header={magic:n.decode(new Uint8Array(e.slice(0,4))),version:t.getUint32(4,!0),length:t.getUint32(8,!0)},this.header.magic!==mh)throw new Error("THREE.GLTFLoader: Unsupported glTF-Binary header.");if(this.header.version<2)throw new Error("THREE.GLTFLoader: Legacy binary file detected.");const r=this.header.length-es,s=new DataView(e,es);let a=0;for(;a<r;){const o=s.getUint32(a,!0);a+=4;const l=s.getUint32(a,!0);if(a+=4,l===cu.JSON){const c=new Uint8Array(e,es+a,o);this.content=n.decode(c)}else if(l===cu.BIN){const c=es+a;this.body=e.slice(c,c+o)}a+=o}if(this.content===null)throw new Error("THREE.GLTFLoader: JSON content not found.")}}class Xx{constructor(e,t){if(!t)throw new Error("THREE.GLTFLoader: No DRACOLoader instance provided.");this.name=qe.KHR_DRACO_MESH_COMPRESSION,this.json=e,this.dracoLoader=t,this.dracoLoader.preload()}decodePrimitive(e,t){const n=this.json,r=this.dracoLoader,s=e.extensions[this.name].bufferView,a=e.extensions[this.name].attributes,o={},l={},c={};for(const h in a){const u=Nl[h]||h.toLowerCase();o[u]=a[h]}for(const h in e.attributes){const u=Nl[h]||h.toLowerCase();if(a[h]!==void 0){const f=n.accessors[e.attributes[h]],p=xr[f.componentType];c[u]=p.name,l[u]=f.normalized===!0}}return t.getDependency("bufferView",s).then(function(h){return new Promise(function(u,f){r.decodeDracoFile(h,function(p){for(const _ in p.attributes){const y=p.attributes[_],g=l[_];g!==void 0&&(y.normalized=g)}u(p)},o,c,zt,f)})})}}class jx{constructor(){this.name=qe.KHR_TEXTURE_TRANSFORM}extendTexture(e,t){return(t.texCoord===void 0||t.texCoord===e.channel)&&t.offset===void 0&&t.rotation===void 0&&t.scale===void 0||(e=e.clone(),t.texCoord!==void 0&&(e.channel=t.texCoord),t.offset!==void 0&&e.offset.fromArray(t.offset),t.rotation!==void 0&&(e.rotation=t.rotation),t.scale!==void 0&&e.repeat.fromArray(t.scale),e.needsUpdate=!0),e}}class qx{constructor(){this.name=qe.KHR_MESH_QUANTIZATION}}class gh extends ws{constructor(e,t,n,r){super(e,t,n,r)}copySampleValue_(e){const t=this.resultBuffer,n=this.sampleValues,r=this.valueSize,s=e*r*3+r;for(let a=0;a!==r;a++)t[a]=n[s+a];return t}interpolate_(e,t,n,r){const s=this.resultBuffer,a=this.sampleValues,o=this.valueSize,l=o*2,c=o*3,h=r-t,u=(n-t)/h,f=u*u,p=f*u,_=e*c,y=_-c,g=-2*p+3*f,m=p-f,E=1-g,w=m-f+u;for(let x=0;x!==o;x++){const T=a[y+x+o],L=a[y+x+l]*h,C=a[_+x+o],R=a[_+x]*h;s[x]=E*T+w*L+g*C+m*R}return s}}const Yx=new En;class Kx extends gh{interpolate_(e,t,n,r){const s=super.interpolate_(e,t,n,r);return Yx.fromArray(s).normalize().toArray(s),s}}const cn={POINTS:0,LINES:1,LINE_LOOP:2,LINE_STRIP:3,TRIANGLES:4,TRIANGLE_STRIP:5,TRIANGLE_FAN:6},xr={5120:Int8Array,5121:Uint8Array,5122:Int16Array,5123:Uint16Array,5125:Uint32Array,5126:Float32Array},du={9728:qt,9729:Tt,9984:Cu,9985:xa,9986:ts,9987:Pn},uu={33071:Cn,33648:Da,10497:_i},Ho={SCALAR:1,VEC2:2,VEC3:3,VEC4:4,MAT2:4,MAT3:9,MAT4:16},Nl={POSITION:"position",NORMAL:"normal",TANGENT:"tangent",TEXCOORD_0:"uv",TEXCOORD_1:"uv1",TEXCOORD_2:"uv2",TEXCOORD_3:"uv3",COLOR_0:"color",WEIGHTS_0:"skinWeight",JOINTS_0:"skinIndex"},ui={scale:"scale",translation:"position",rotation:"quaternion",weights:"morphTargetInfluences"},$x={CUBICSPLINE:void 0,LINEAR:_s,STEP:gs},Go={OPAQUE:"OPAQUE",MASK:"MASK",BLEND:"BLEND"};function Zx(i){return i.DefaultMaterial===void 0&&(i.DefaultMaterial=new Dn({color:16777215,emissive:0,metalness:1,roughness:1,transparent:!1,depthTest:!0,side:ei})),i.DefaultMaterial}function Ai(i,e,t){for(const n in t.extensions)i[n]===void 0&&(e.userData.gltfExtensions=e.userData.gltfExtensions||{},e.userData.gltfExtensions[n]=t.extensions[n])}function Xn(i,e){e.extras!==void 0&&(typeof e.extras=="object"?Object.assign(i.userData,e.extras):console.warn("THREE.GLTFLoader: Ignoring primitive type .extras, "+e.extras))}function Jx(i,e,t){let n=!1,r=!1,s=!1;for(let c=0,h=e.length;c<h;c++){const u=e[c];if(u.POSITION!==void 0&&(n=!0),u.NORMAL!==void 0&&(r=!0),u.COLOR_0!==void 0&&(s=!0),n&&r&&s)break}if(!n&&!r&&!s)return Promise.resolve(i);const a=[],o=[],l=[];for(let c=0,h=e.length;c<h;c++){const u=e[c];if(n){const f=u.POSITION!==void 0?t.getDependency("accessor",u.POSITION):i.attributes.position;a.push(f)}if(r){const f=u.NORMAL!==void 0?t.getDependency("accessor",u.NORMAL):i.attributes.normal;o.push(f)}if(s){const f=u.COLOR_0!==void 0?t.getDependency("accessor",u.COLOR_0):i.attributes.color;l.push(f)}}return Promise.all([Promise.all(a),Promise.all(o),Promise.all(l)]).then(function(c){const h=c[0],u=c[1],f=c[2];return n&&(i.morphAttributes.position=h),r&&(i.morphAttributes.normal=u),s&&(i.morphAttributes.color=f),i.morphTargetsRelative=!0,i})}function Qx(i,e){if(i.updateMorphTargets(),e.weights!==void 0)for(let t=0,n=e.weights.length;t<n;t++)i.morphTargetInfluences[t]=e.weights[t];if(e.extras&&Array.isArray(e.extras.targetNames)){const t=e.extras.targetNames;if(i.morphTargetInfluences.length===t.length){i.morphTargetDictionary={};for(let n=0,r=t.length;n<r;n++)i.morphTargetDictionary[t[n]]=n}else console.warn("THREE.GLTFLoader: Invalid extras.targetNames length. Ignoring names.")}}function ev(i){let e;const t=i.extensions&&i.extensions[qe.KHR_DRACO_MESH_COMPRESSION];if(t?e="draco:"+t.bufferView+":"+t.indices+":"+Vo(t.attributes):e=i.indices+":"+Vo(i.attributes)+":"+i.mode,i.targets!==void 0)for(let n=0,r=i.targets.length;n<r;n++)e+=":"+Vo(i.targets[n]);return e}function Vo(i){let e="";const t=Object.keys(i).sort();for(let n=0,r=t.length;n<r;n++)e+=t[n]+":"+i[t[n]]+";";return e}function Ul(i){switch(i){case Int8Array:return 1/127;case Uint8Array:return 1/255;case Int16Array:return 1/32767;case Uint16Array:return 1/65535;default:throw new Error("THREE.GLTFLoader: Unsupported normalized accessor component type.")}}function tv(i){return i.search(/\.jpe?g($|\?)/i)>0||i.search(/^data\:image\/jpeg/)===0?"image/jpeg":i.search(/\.webp($|\?)/i)>0||i.search(/^data\:image\/webp/)===0?"image/webp":i.search(/\.ktx2($|\?)/i)>0||i.search(/^data\:image\/ktx2/)===0?"image/ktx2":"image/png"}const nv=new De;class iv{constructor(e={},t={}){this.json=e,this.extensions={},this.plugins={},this.options=t,this.cache=new Ex,this.associations=new Map,this.primitiveCache={},this.nodeCache={},this.meshCache={refs:{},uses:{}},this.cameraCache={refs:{},uses:{}},this.lightCache={refs:{},uses:{}},this.sourceCache={},this.textureCache={},this.nodeNamesUsed={};let n=!1,r=-1,s=!1,a=-1;if(typeof navigator<"u"){const o=navigator.userAgent;n=/^((?!chrome|android).)*safari/i.test(o)===!0;const l=o.match(/Version\/(\d+)/);r=n&&l?parseInt(l[1],10):-1,s=o.indexOf("Firefox")>-1,a=s?o.match(/Firefox\/([0-9]+)\./)[1]:-1}typeof createImageBitmap>"u"||n&&r<17||s&&a<98?this.textureLoader=new ih(this.options.manager):this.textureLoader=new mm(this.options.manager),this.textureLoader.setCrossOrigin(this.options.crossOrigin),this.textureLoader.setRequestHeader(this.options.requestHeader),this.fileLoader=new cc(this.options.manager),this.fileLoader.setResponseType("arraybuffer"),this.options.crossOrigin==="use-credentials"&&this.fileLoader.setWithCredentials(!0)}setExtensions(e){this.extensions=e}setPlugins(e){this.plugins=e}parse(e,t){const n=this,r=this.json,s=this.extensions;this.cache.removeAll(),this.nodeCache={},this._invokeAll(function(a){return a._markDefs&&a._markDefs()}),Promise.all(this._invokeAll(function(a){return a.beforeRoot&&a.beforeRoot()})).then(function(){return Promise.all([n.getDependencies("scene"),n.getDependencies("animation"),n.getDependencies("camera")])}).then(function(a){const o={scene:a[0][r.scene||0],scenes:a[0],animations:a[1],cameras:a[2],asset:r.asset,parser:n,userData:{}};return Ai(s,o,r),Xn(o,r),Promise.all(n._invokeAll(function(l){return l.afterRoot&&l.afterRoot(o)})).then(function(){for(const l of o.scenes)l.updateMatrixWorld();e(o)})}).catch(t)}_markDefs(){const e=this.json.nodes||[],t=this.json.skins||[],n=this.json.meshes||[];for(let r=0,s=t.length;r<s;r++){const a=t[r].joints;for(let o=0,l=a.length;o<l;o++)e[a[o]].isBone=!0}for(let r=0,s=e.length;r<s;r++){const a=e[r];a.mesh!==void 0&&(this._addNodeRef(this.meshCache,a.mesh),a.skin!==void 0&&(n[a.mesh].isSkinnedMesh=!0)),a.camera!==void 0&&this._addNodeRef(this.cameraCache,a.camera)}}_addNodeRef(e,t){t!==void 0&&(e.refs[t]===void 0&&(e.refs[t]=e.uses[t]=0),e.refs[t]++)}_getNodeRef(e,t,n){if(e.refs[t]<=1)return n;const r=n.clone(),s=(a,o)=>{const l=this.associations.get(a);l!=null&&this.associations.set(o,l);for(const[c,h]of a.children.entries())s(h,o.children[c])};return s(n,r),r.name+="_instance_"+e.uses[t]++,r}_invokeOne(e){const t=Object.values(this.plugins);t.push(this);for(let n=0;n<t.length;n++){const r=e(t[n]);if(r)return r}return null}_invokeAll(e){const t=Object.values(this.plugins);t.unshift(this);const n=[];for(let r=0;r<t.length;r++){const s=e(t[r]);s&&n.push(s)}return n}getDependency(e,t){const n=e+":"+t;let r=this.cache.get(n);if(!r){switch(e){case"scene":r=this.loadScene(t);break;case"node":r=this._invokeOne(function(s){return s.loadNode&&s.loadNode(t)});break;case"mesh":r=this._invokeOne(function(s){return s.loadMesh&&s.loadMesh(t)});break;case"accessor":r=this.loadAccessor(t);break;case"bufferView":r=this._invokeOne(function(s){return s.loadBufferView&&s.loadBufferView(t)});break;case"buffer":r=this.loadBuffer(t);break;case"material":r=this._invokeOne(function(s){return s.loadMaterial&&s.loadMaterial(t)});break;case"texture":r=this._invokeOne(function(s){return s.loadTexture&&s.loadTexture(t)});break;case"skin":r=this.loadSkin(t);break;case"animation":r=this._invokeOne(function(s){return s.loadAnimation&&s.loadAnimation(t)});break;case"camera":r=this.loadCamera(t);break;default:if(r=this._invokeOne(function(s){return s!=this&&s.getDependency&&s.getDependency(e,t)}),!r)throw new Error("Unknown type: "+e);break}this.cache.add(n,r)}return r}getDependencies(e){let t=this.cache.get(e);if(!t){const n=this,r=this.json[e+(e==="mesh"?"es":"s")]||[];t=Promise.all(r.map(function(s,a){return n.getDependency(e,a)})),this.cache.add(e,t)}return t}loadBuffer(e){const t=this.json.buffers[e],n=this.fileLoader;if(t.type&&t.type!=="arraybuffer")throw new Error("THREE.GLTFLoader: "+t.type+" buffer type is not supported.");if(t.uri===void 0&&e===0)return Promise.resolve(this.extensions[qe.KHR_BINARY_GLTF].body);const r=this.options;return new Promise(function(s,a){n.load(cs.resolveURL(t.uri,r.path),s,void 0,function(){a(new Error('THREE.GLTFLoader: Failed to load buffer "'+t.uri+'".'))})})}loadBufferView(e){const t=this.json.bufferViews[e];return this.getDependency("buffer",t.buffer).then(function(n){const r=t.byteLength||0,s=t.byteOffset||0;return n.slice(s,s+r)})}loadAccessor(e){const t=this,n=this.json,r=this.json.accessors[e];if(r.bufferView===void 0&&r.sparse===void 0){const a=Ho[r.type],o=xr[r.componentType],l=r.normalized===!0,c=new o(r.count*a);return Promise.resolve(new Ot(c,a,l))}const s=[];return r.bufferView!==void 0?s.push(this.getDependency("bufferView",r.bufferView)):s.push(null),r.sparse!==void 0&&(s.push(this.getDependency("bufferView",r.sparse.indices.bufferView)),s.push(this.getDependency("bufferView",r.sparse.values.bufferView))),Promise.all(s).then(function(a){const o=a[0],l=Ho[r.type],c=xr[r.componentType],h=c.BYTES_PER_ELEMENT,u=h*l,f=r.byteOffset||0,p=r.bufferView!==void 0?n.bufferViews[r.bufferView].byteStride:void 0,_=r.normalized===!0;let y,g;if(p&&p!==u){const m=Math.floor(f/p),E="InterleavedBuffer:"+r.bufferView+":"+r.componentType+":"+m+":"+r.count;let w=t.cache.get(E);w||(y=new c(o,m*p,r.count*p/h),w=new Yu(y,p/h),t.cache.add(E,w)),g=new xs(w,l,f%p/h,_)}else o===null?y=new c(r.count*l):y=new c(o,f,r.count*l),g=new Ot(y,l,_);if(r.sparse!==void 0){const m=Ho.SCALAR,E=xr[r.sparse.indices.componentType],w=r.sparse.indices.byteOffset||0,x=r.sparse.values.byteOffset||0,T=new E(a[1],w,r.sparse.count*m),L=new c(a[2],x,r.sparse.count*l);o!==null&&(g=new Ot(g.array.slice(),g.itemSize,g.normalized)),g.normalized=!1;for(let C=0,R=T.length;C<R;C++){const v=T[C];if(g.setX(v,L[C*l]),l>=2&&g.setY(v,L[C*l+1]),l>=3&&g.setZ(v,L[C*l+2]),l>=4&&g.setW(v,L[C*l+3]),l>=5)throw new Error("THREE.GLTFLoader: Unsupported itemSize in sparse BufferAttribute.")}g.normalized=_}return g})}loadTexture(e){const t=this.json,n=this.options,s=t.textures[e].source,a=t.images[s];let o=this.textureLoader;if(a.uri){const l=n.manager.getHandler(a.uri);l!==null&&(o=l)}return this.loadTextureImage(e,s,o)}loadTextureImage(e,t,n){const r=this,s=this.json,a=s.textures[e],o=s.images[t],l=(o.uri||o.bufferView)+":"+a.sampler;if(this.textureCache[l])return this.textureCache[l];const c=this.loadImageSource(t,n).then(function(h){h.flipY=!1,h.name=a.name||o.name||"",h.name===""&&typeof o.uri=="string"&&o.uri.startsWith("data:image/")===!1&&(h.name=o.uri);const f=(s.samplers||{})[a.sampler]||{};return h.magFilter=du[f.magFilter]||Tt,h.minFilter=du[f.minFilter]||Pn,h.wrapS=uu[f.wrapS]||_i,h.wrapT=uu[f.wrapT]||_i,h.generateMipmaps=!h.isCompressedTexture&&h.minFilter!==qt&&h.minFilter!==Tt,r.associations.set(h,{textures:e}),h}).catch(function(){return null});return this.textureCache[l]=c,c}loadImageSource(e,t){const n=this,r=this.json,s=this.options;if(this.sourceCache[e]!==void 0)return this.sourceCache[e].then(u=>u.clone());const a=r.images[e],o=self.URL||self.webkitURL;let l=a.uri||"",c=!1;if(a.bufferView!==void 0)l=n.getDependency("bufferView",a.bufferView).then(function(u){c=!0;const f=new Blob([u],{type:a.mimeType});return l=o.createObjectURL(f),l});else if(a.uri===void 0)throw new Error("THREE.GLTFLoader: Image "+e+" is missing URI and bufferView");const h=Promise.resolve(l).then(function(u){return new Promise(function(f,p){let _=f;t.isImageBitmapLoader===!0&&(_=function(y){const g=new Ct(y);g.needsUpdate=!0,f(g)}),t.load(cs.resolveURL(u,s.path),_,void 0,p)})}).then(function(u){return c===!0&&o.revokeObjectURL(l),Xn(u,a),u.userData.mimeType=a.mimeType||tv(a.uri),u}).catch(function(u){throw console.error("THREE.GLTFLoader: Couldn't load texture",l),u});return this.sourceCache[e]=h,h}assignTexture(e,t,n,r){const s=this;return this.getDependency("texture",n.index).then(function(a){if(!a)return null;if(n.texCoord!==void 0&&n.texCoord>0&&(a=a.clone(),a.channel=n.texCoord),s.extensions[qe.KHR_TEXTURE_TRANSFORM]){const o=n.extensions!==void 0?n.extensions[qe.KHR_TEXTURE_TRANSFORM]:void 0;if(o){const l=s.associations.get(a);a=s.extensions[qe.KHR_TEXTURE_TRANSFORM].extendTexture(a,o),s.associations.set(a,l)}}return r!==void 0&&(a.colorSpace=r),e[t]=a,a})}assignFinalMaterial(e){const t=e.geometry;let n=e.material;const r=t.attributes.tangent===void 0,s=t.attributes.color!==void 0,a=t.attributes.normal===void 0;if(e.isPoints){const o="PointsMaterial:"+n.uuid;let l=this.cache.get(o);l||(l=new ac,hn.prototype.copy.call(l,n),l.color.copy(n.color),l.map=n.map,l.sizeAttenuation=!1,this.cache.add(o,l)),n=l}else if(e.isLine){const o="LineBasicMaterial:"+n.uuid;let l=this.cache.get(o);l||(l=new Fn,hn.prototype.copy.call(l,n),l.color.copy(n.color),l.map=n.map,this.cache.add(o,l)),n=l}if(r||s||a){let o="ClonedMaterial:"+n.uuid+":";r&&(o+="derivative-tangents:"),s&&(o+="vertex-colors:"),a&&(o+="flat-shading:");let l=this.cache.get(o);l||(l=n.clone(),s&&(l.vertexColors=!0),a&&(l.flatShading=!0),r&&(l.normalScale&&(l.normalScale.y*=-1),l.clearcoatNormalScale&&(l.clearcoatNormalScale.y*=-1)),this.cache.add(o,l),this.associations.set(l,this.associations.get(n))),n=l}e.material=n}getMaterialType(){return Dn}loadMaterial(e){const t=this,n=this.json,r=this.extensions,s=n.materials[e];let a;const o={},l=s.extensions||{},c=[];if(l[qe.KHR_MATERIALS_UNLIT]){const u=r[qe.KHR_MATERIALS_UNLIT];a=u.getMaterialType(),c.push(u.extendParams(o,s,t))}else{const u=s.pbrMetallicRoughness||{};if(o.color=new Ee(1,1,1),o.opacity=1,Array.isArray(u.baseColorFactor)){const f=u.baseColorFactor;o.color.setRGB(f[0],f[1],f[2],zt),o.opacity=f[3]}u.baseColorTexture!==void 0&&c.push(t.assignTexture(o,"map",u.baseColorTexture,Et)),o.metalness=u.metallicFactor!==void 0?u.metallicFactor:1,o.roughness=u.roughnessFactor!==void 0?u.roughnessFactor:1,u.metallicRoughnessTexture!==void 0&&(c.push(t.assignTexture(o,"metalnessMap",u.metallicRoughnessTexture)),c.push(t.assignTexture(o,"roughnessMap",u.metallicRoughnessTexture))),a=this._invokeOne(function(f){return f.getMaterialType&&f.getMaterialType(e)}),c.push(Promise.all(this._invokeAll(function(f){return f.extendMaterialParams&&f.extendMaterialParams(e,o)})))}s.doubleSided===!0&&(o.side=un);const h=s.alphaMode||Go.OPAQUE;if(h===Go.BLEND?(o.transparent=!0,o.depthWrite=!1):(o.transparent=!1,h===Go.MASK&&(o.alphaTest=s.alphaCutoff!==void 0?s.alphaCutoff:.5)),s.normalTexture!==void 0&&a!==Kn&&(c.push(t.assignTexture(o,"normalMap",s.normalTexture)),o.normalScale=new xe(1,1),s.normalTexture.scale!==void 0)){const u=s.normalTexture.scale;o.normalScale.set(u,u)}if(s.occlusionTexture!==void 0&&a!==Kn&&(c.push(t.assignTexture(o,"aoMap",s.occlusionTexture)),s.occlusionTexture.strength!==void 0&&(o.aoMapIntensity=s.occlusionTexture.strength)),s.emissiveFactor!==void 0&&a!==Kn){const u=s.emissiveFactor;o.emissive=new Ee().setRGB(u[0],u[1],u[2],zt)}return s.emissiveTexture!==void 0&&a!==Kn&&c.push(t.assignTexture(o,"emissiveMap",s.emissiveTexture,Et)),Promise.all(c).then(function(){const u=new a(o);return s.name&&(u.name=s.name),Xn(u,s),t.associations.set(u,{materials:e}),s.extensions&&Ai(r,u,s),u})}createUniqueName(e){const t=at.sanitizeNodeName(e||"");return t in this.nodeNamesUsed?t+"_"+ ++this.nodeNamesUsed[t]:(this.nodeNamesUsed[t]=0,t)}loadGeometries(e){const t=this,n=this.extensions,r=this.primitiveCache;function s(o){return n[qe.KHR_DRACO_MESH_COMPRESSION].decodePrimitive(o,t).then(function(l){return hu(l,o,t)})}const a=[];for(let o=0,l=e.length;o<l;o++){const c=e[o],h=ev(c),u=r[h];if(u)a.push(u.promise);else{let f;c.extensions&&c.extensions[qe.KHR_DRACO_MESH_COMPRESSION]?f=s(c):f=hu(new yt,c,t),r[h]={primitive:c,promise:f},a.push(f)}}return Promise.all(a)}loadMesh(e){const t=this,n=this.json,r=this.extensions,s=n.meshes[e],a=s.primitives,o=[];for(let l=0,c=a.length;l<c;l++){const h=a[l].material===void 0?Zx(this.cache):this.getDependency("material",a[l].material);o.push(h)}return o.push(t.loadGeometries(a)),Promise.all(o).then(function(l){const c=l.slice(0,l.length-1),h=l[l.length-1],u=[];for(let p=0,_=h.length;p<_;p++){const y=h[p],g=a[p];let m;const E=c[p];if(g.mode===cn.TRIANGLES||g.mode===cn.TRIANGLE_STRIP||g.mode===cn.TRIANGLE_FAN||g.mode===void 0)m=s.isSkinnedMesh===!0?new Op(y,E):new ut(y,E),m.isSkinnedMesh===!0&&m.normalizeSkinWeights(),g.mode===cn.TRIANGLE_STRIP?m.geometry=lu(m.geometry,Ou):g.mode===cn.TRIANGLE_FAN&&(m.geometry=lu(m.geometry,Rl));else if(g.mode===cn.LINES)m=new ni(y,E);else if(g.mode===cn.LINE_STRIP)m=new sc(y,E);else if(g.mode===cn.LINE_LOOP)m=new Vp(y,E);else if(g.mode===cn.POINTS)m=new Ju(y,E);else throw new Error("THREE.GLTFLoader: Primitive mode unsupported: "+g.mode);Object.keys(m.geometry.morphAttributes).length>0&&Qx(m,s),m.name=t.createUniqueName(s.name||"mesh_"+e),Xn(m,s),g.extensions&&Ai(r,m,g),t.assignFinalMaterial(m),u.push(m)}for(let p=0,_=u.length;p<_;p++)t.associations.set(u[p],{meshes:e,primitives:p});if(u.length===1)return s.extensions&&Ai(r,u[0],s),u[0];const f=new At;s.extensions&&Ai(r,f,s),t.associations.set(f,{meshes:e});for(let p=0,_=u.length;p<_;p++)f.add(u[p]);return f})}loadCamera(e){let t;const n=this.json.cameras[e],r=n[n.type];if(!r){console.warn("THREE.GLTFLoader: Missing camera parameters.");return}return n.type==="perspective"?t=new Xt(wn.radToDeg(r.yfov),r.aspectRatio||1,r.znear||1,r.zfar||2e6):n.type==="orthographic"&&(t=new uc(-r.xmag,r.xmag,r.ymag,-r.ymag,r.znear,r.zfar)),n.name&&(t.name=this.createUniqueName(n.name)),Xn(t,n),Promise.resolve(t)}loadSkin(e){const t=this.json.skins[e],n=[];for(let r=0,s=t.joints.length;r<s;r++)n.push(this._loadNodeShallow(t.joints[r]));return t.inverseBindMatrices!==void 0?n.push(this.getDependency("accessor",t.inverseBindMatrices)):n.push(null),Promise.all(n).then(function(r){const s=r.pop(),a=r,o=[],l=[];for(let c=0,h=a.length;c<h;c++){const u=a[c];if(u){o.push(u);const f=new De;s!==null&&f.fromArray(s.array,c*16),l.push(f)}else console.warn('THREE.GLTFLoader: Joint "%s" could not be found.',t.joints[c])}return new rc(o,l)})}loadAnimation(e){const t=this.json,n=this,r=t.animations[e],s=r.name?r.name:"animation_"+e,a=[],o=[],l=[],c=[],h=[];for(let u=0,f=r.channels.length;u<f;u++){const p=r.channels[u],_=r.samplers[p.sampler],y=p.target,g=y.node,m=r.parameters!==void 0?r.parameters[_.input]:_.input,E=r.parameters!==void 0?r.parameters[_.output]:_.output;y.node!==void 0&&(a.push(this.getDependency("node",g)),o.push(this.getDependency("accessor",m)),l.push(this.getDependency("accessor",E)),c.push(_),h.push(y))}return Promise.all([Promise.all(a),Promise.all(o),Promise.all(l),Promise.all(c),Promise.all(h)]).then(function(u){const f=u[0],p=u[1],_=u[2],y=u[3],g=u[4],m=[];for(let E=0,w=f.length;E<w;E++){const x=f[E],T=p[E],L=_[E],C=y[E],R=g[E];if(x===void 0)continue;x.updateMatrix&&x.updateMatrix();const v=n._createAnimationTracks(x,T,L,C,R);if(v)for(let b=0;b<v.length;b++)m.push(v[b])}return new tm(s,void 0,m)})}createNodeMesh(e){const t=this.json,n=this,r=t.nodes[e];return r.mesh===void 0?null:n.getDependency("mesh",r.mesh).then(function(s){const a=n._getNodeRef(n.meshCache,r.mesh,s);return r.weights!==void 0&&a.traverse(function(o){if(o.isMesh)for(let l=0,c=r.weights.length;l<c;l++)o.morphTargetInfluences[l]=r.weights[l]}),a})}loadNode(e){const t=this.json,n=this,r=t.nodes[e],s=n._loadNodeShallow(e),a=[],o=r.children||[];for(let c=0,h=o.length;c<h;c++)a.push(n.getDependency("node",o[c]));const l=r.skin===void 0?Promise.resolve(null):n.getDependency("skin",r.skin);return Promise.all([s,Promise.all(a),l]).then(function(c){const h=c[0],u=c[1],f=c[2];f!==null&&h.traverse(function(p){p.isSkinnedMesh&&p.bind(f,nv)});for(let p=0,_=u.length;p<_;p++)h.add(u[p]);return h})}_loadNodeShallow(e){const t=this.json,n=this.extensions,r=this;if(this.nodeCache[e]!==void 0)return this.nodeCache[e];const s=t.nodes[e],a=s.name?r.createUniqueName(s.name):"",o=[],l=r._invokeOne(function(c){return c.createNodeMesh&&c.createNodeMesh(e)});return l&&o.push(l),s.camera!==void 0&&o.push(r.getDependency("camera",s.camera).then(function(c){return r._getNodeRef(r.cameraCache,s.camera,c)})),r._invokeAll(function(c){return c.createNodeAttachment&&c.createNodeAttachment(e)}).forEach(function(c){o.push(c)}),this.nodeCache[e]=Promise.all(o).then(function(c){let h;if(s.isBone===!0?h=new Zu:c.length>1?h=new At:c.length===1?h=c[0]:h=new pt,h!==c[0])for(let u=0,f=c.length;u<f;u++)h.add(c[u]);if(s.name&&(h.userData.name=s.name,h.name=a),Xn(h,s),s.extensions&&Ai(n,h,s),s.matrix!==void 0){const u=new De;u.fromArray(s.matrix),h.applyMatrix4(u)}else s.translation!==void 0&&h.position.fromArray(s.translation),s.rotation!==void 0&&h.quaternion.fromArray(s.rotation),s.scale!==void 0&&h.scale.fromArray(s.scale);if(!r.associations.has(h))r.associations.set(h,{});else if(s.mesh!==void 0&&r.meshCache.refs[s.mesh]>1){const u=r.associations.get(h);r.associations.set(h,{...u})}return r.associations.get(h).nodes=e,h}),this.nodeCache[e]}loadScene(e){const t=this.extensions,n=this.json.scenes[e],r=this,s=new At;n.name&&(s.name=r.createUniqueName(n.name)),Xn(s,n),n.extensions&&Ai(t,s,n);const a=n.nodes||[],o=[];for(let l=0,c=a.length;l<c;l++)o.push(r.getDependency("node",a[l]));return Promise.all(o).then(function(l){for(let h=0,u=l.length;h<u;h++)s.add(l[h]);const c=h=>{const u=new Map;for(const[f,p]of r.associations)(f instanceof hn||f instanceof Ct)&&u.set(f,p);return h.traverse(f=>{const p=r.associations.get(f);p!=null&&u.set(f,p)}),u};return r.associations=c(s),s})}_createAnimationTracks(e,t,n,r,s){const a=[],o=e.name?e.name:e.uuid,l=[];ui[s.path]===ui.weights?e.traverse(function(f){f.morphTargetInfluences&&l.push(f.name?f.name:f.uuid)}):l.push(o);let c;switch(ui[s.path]){case ui.weights:c=Ar;break;case ui.rotation:c=Rr;break;case ui.translation:case ui.scale:c=Cr;break;default:n.itemSize===1?c=Ar:c=Cr;break}const h=r.interpolation!==void 0?$x[r.interpolation]:_s,u=this._getArrayFromAccessor(n);for(let f=0,p=l.length;f<p;f++){const _=new c(l[f]+"."+ui[s.path],t.array,u,h);r.interpolation==="CUBICSPLINE"&&this._createCubicSplineTrackInterpolant(_),a.push(_)}return a}_getArrayFromAccessor(e){let t=e.array;if(e.normalized){const n=Ul(t.constructor),r=new Float32Array(t.length);for(let s=0,a=t.length;s<a;s++)r[s]=t[s]*n;t=r}return t}_createCubicSplineTrackInterpolant(e){e.createInterpolant=function(n){const r=this instanceof Rr?Kx:gh;return new r(this.times,this.values,this.getValueSize()/3,n)},e.createInterpolant.isInterpolantFactoryMethodGLTFCubicSpline=!0}}function rv(i,e,t){const n=e.attributes,r=new kt;if(n.POSITION!==void 0){const o=t.json.accessors[n.POSITION],l=o.min,c=o.max;if(l!==void 0&&c!==void 0){if(r.set(new P(l[0],l[1],l[2]),new P(c[0],c[1],c[2])),o.normalized){const h=Ul(xr[o.componentType]);r.min.multiplyScalar(h),r.max.multiplyScalar(h)}}else{console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.");return}}else return;const s=e.targets;if(s!==void 0){const o=new P,l=new P;for(let c=0,h=s.length;c<h;c++){const u=s[c];if(u.POSITION!==void 0){const f=t.json.accessors[u.POSITION],p=f.min,_=f.max;if(p!==void 0&&_!==void 0){if(l.setX(Math.max(Math.abs(p[0]),Math.abs(_[0]))),l.setY(Math.max(Math.abs(p[1]),Math.abs(_[1]))),l.setZ(Math.max(Math.abs(p[2]),Math.abs(_[2]))),f.normalized){const y=Ul(xr[f.componentType]);l.multiplyScalar(y)}o.max(l)}else console.warn("THREE.GLTFLoader: Missing min/max properties for accessor POSITION.")}}r.expandByVector(o)}i.boundingBox=r;const a=new Un;r.getCenter(a.center),a.radius=r.min.distanceTo(r.max)/2,i.boundingSphere=a}function hu(i,e,t){const n=e.attributes,r=[];function s(a,o){return t.getDependency("accessor",a).then(function(l){i.setAttribute(o,l)})}for(const a in n){const o=Nl[a]||a.toLowerCase();o in i.attributes||r.push(s(n[a],o))}if(e.indices!==void 0&&!i.index){const a=t.getDependency("accessor",e.indices).then(function(o){i.setIndex(o)});r.push(a)}return Je.workingColorSpace!==zt&&"COLOR_0"in n&&console.warn(`THREE.GLTFLoader: Converting vertex colors from "srgb-linear" to "${Je.workingColorSpace}" not supported.`),Xn(i,e),rv(i,e,t),Promise.all(r).then(function(){return e.targets!==void 0?Jx(i,e.targets,t):i})}class sv extends lm{constructor(e){super(e),this.type=In}parse(e){const a=function(R,v){switch(R){case 1:throw new Error("THREE.RGBELoader: Read Error: "+(v||""));case 2:throw new Error("THREE.RGBELoader: Write Error: "+(v||""));case 3:throw new Error("THREE.RGBELoader: Bad File Format: "+(v||""));default:case 4:throw new Error("THREE.RGBELoader: Memory Error: "+(v||""))}},u=function(R,v,b){v=v||1024;let U=R.pos,z=-1,B=0,V="",G=String.fromCharCode.apply(null,new Uint16Array(R.subarray(U,U+128)));for(;0>(z=G.indexOf(`
`))&&B<v&&U<R.byteLength;)V+=G,B+=G.length,U+=128,G+=String.fromCharCode.apply(null,new Uint16Array(R.subarray(U,U+128)));return-1<z?(R.pos+=B+z+1,V+G.slice(0,z)):!1},f=function(R){const v=/^#\?(\S+)/,b=/^\s*GAMMA\s*=\s*(\d+(\.\d+)?)\s*$/,A=/^\s*EXPOSURE\s*=\s*(\d+(\.\d+)?)\s*$/,U=/^\s*FORMAT=(\S+)\s*$/,z=/^\s*\-Y\s+(\d+)\s+\+X\s+(\d+)\s*$/,B={valid:0,string:"",comments:"",programtype:"RGBE",format:"",gamma:1,exposure:1,width:0,height:0};let V,G;for((R.pos>=R.byteLength||!(V=u(R)))&&a(1,"no header found"),(G=V.match(v))||a(3,"bad initial token"),B.valid|=1,B.programtype=G[1],B.string+=V+`
`;V=u(R),V!==!1;){if(B.string+=V+`
`,V.charAt(0)==="#"){B.comments+=V+`
`;continue}if((G=V.match(b))&&(B.gamma=parseFloat(G[1])),(G=V.match(A))&&(B.exposure=parseFloat(G[1])),(G=V.match(U))&&(B.valid|=2,B.format=G[1]),(G=V.match(z))&&(B.valid|=4,B.height=parseInt(G[1],10),B.width=parseInt(G[2],10)),B.valid&2&&B.valid&4)break}return B.valid&2||a(3,"missing format specifier"),B.valid&4||a(3,"missing image size specifier"),B},p=function(R,v,b){const A=v;if(A<8||A>32767||R[0]!==2||R[1]!==2||R[2]&128)return new Uint8Array(R);A!==(R[2]<<8|R[3])&&a(3,"wrong scanline width");const U=new Uint8Array(4*v*b);U.length||a(4,"unable to allocate buffer space");let z=0,B=0;const V=4*A,G=new Uint8Array(4),J=new Uint8Array(V);let j=b;for(;j>0&&B<R.byteLength;){B+4>R.byteLength&&a(1),G[0]=R[B++],G[1]=R[B++],G[2]=R[B++],G[3]=R[B++],(G[0]!=2||G[1]!=2||(G[2]<<8|G[3])!=A)&&a(3,"bad rgbe scanline format");let re=0,le;for(;re<V&&B<R.byteLength;){le=R[B++];const Ne=le>128;if(Ne&&(le-=128),(le===0||re+le>V)&&a(3,"bad scanline data"),Ne){const Ze=R[B++];for(let it=0;it<le;it++)J[re++]=Ze}else J.set(R.subarray(B,B+le),re),re+=le,B+=le}const Re=A;for(let Ne=0;Ne<Re;Ne++){let Ze=0;U[z]=J[Ne+Ze],Ze+=A,U[z+1]=J[Ne+Ze],Ze+=A,U[z+2]=J[Ne+Ze],Ze+=A,U[z+3]=J[Ne+Ze],z+=4}j--}return U},_=function(R,v,b,A){const U=R[v+3],z=Math.pow(2,U-128)/255;b[A+0]=R[v+0]*z,b[A+1]=R[v+1]*z,b[A+2]=R[v+2]*z,b[A+3]=1},y=function(R,v,b,A){const U=R[v+3],z=Math.pow(2,U-128)/255;b[A+0]=ns.toHalfFloat(Math.min(R[v+0]*z,65504)),b[A+1]=ns.toHalfFloat(Math.min(R[v+1]*z,65504)),b[A+2]=ns.toHalfFloat(Math.min(R[v+2]*z,65504)),b[A+3]=ns.toHalfFloat(1)},g=new Uint8Array(e);g.pos=0;const m=f(g),E=m.width,w=m.height,x=p(g.subarray(g.pos),E,w);let T,L,C;switch(this.type){case $t:C=x.length/4;const R=new Float32Array(C*4);for(let b=0;b<C;b++)_(x,b*4,R,b*4);T=R,L=$t;break;case In:C=x.length/4;const v=new Uint16Array(C*4);for(let b=0;b<C;b++)y(x,b*4,v,b*4);T=v,L=In;break;default:throw new Error("THREE.RGBELoader: Unsupported type: "+this.type)}return{width:E,height:w,data:T,header:m.string,gamma:m.gamma,exposure:m.exposure,type:L}}setDataType(e){return this.type=e,this}load(e,t,n,r){function s(a,o){switch(a.type){case $t:case In:a.colorSpace=zt,a.minFilter=Tt,a.magFilter=Tt,a.generateMipmaps=!1,a.flipY=!0;break}t&&t(a,o)}return super.load(e,s,n,r)}}class av extends qu{constructor(){super();const e=new yi;e.deleteAttribute("uv");const t=new Dn({side:jt}),n=new Dn,r=new rh(16777215,900,28,2);r.position.set(.418,16.199,.3),this.add(r);const s=new ut(e,t);s.position.set(-.757,13.219,.717),s.scale.set(31.713,28.305,28.591),this.add(s);const a=new bs(e,n,6),o=new pt;o.position.set(-10.906,2.009,1.846),o.rotation.set(0,-.195,0),o.scale.set(2.328,7.905,4.651),o.updateMatrix(),a.setMatrixAt(0,o.matrix),o.position.set(-5.607,-.754,-.758),o.rotation.set(0,.994,0),o.scale.set(1.97,1.534,3.955),o.updateMatrix(),a.setMatrixAt(1,o.matrix),o.position.set(6.167,.857,7.803),o.rotation.set(0,.561,0),o.scale.set(3.927,6.285,3.687),o.updateMatrix(),a.setMatrixAt(2,o.matrix),o.position.set(-2.017,.018,6.124),o.rotation.set(0,.333,0),o.scale.set(2.002,4.566,2.064),o.updateMatrix(),a.setMatrixAt(3,o.matrix),o.position.set(2.291,-.756,-2.621),o.rotation.set(0,-.286,0),o.scale.set(1.546,1.552,1.496),o.updateMatrix(),a.setMatrixAt(4,o.matrix),o.position.set(-2.193,-.369,-5.547),o.rotation.set(0,.516,0),o.scale.set(3.875,3.487,2.986),o.updateMatrix(),a.setMatrixAt(5,o.matrix),this.add(a);const l=new ut(e,or(50));l.position.set(-16.116,14.37,8.208),l.scale.set(.1,2.428,2.739),this.add(l);const c=new ut(e,or(50));c.position.set(-16.109,18.021,-8.207),c.scale.set(.1,2.425,2.751),this.add(c);const h=new ut(e,or(17));h.position.set(14.904,12.198,-1.832),h.scale.set(.15,4.265,6.331),this.add(h);const u=new ut(e,or(43));u.position.set(-.462,8.89,14.52),u.scale.set(4.38,5.441,.088),this.add(u);const f=new ut(e,or(20));f.position.set(3.235,11.486,-12.541),f.scale.set(2.5,2,.1),this.add(f);const p=new ut(e,or(100));p.position.set(0,20,0),p.scale.set(1,.1,1),this.add(p)}dispose(){const e=new Set;this.traverse(t=>{t.isMesh&&(e.add(t.geometry),e.add(t.material))});for(const t of e)t.dispose()}}function or(i){return new Xp({color:0,emissive:16777215,emissiveIntensity:i})}class ov{constructor(e,t,n,r,s=()=>{}){this.manifest=e,this.overview=t,this.fetchJson=n,this.onCommit=r,this.onStatus=s,this.cache=new Map,this.generation=0,this.key=null,this.status={ready:!0,pending:0,failed:0,generation:0,loaded_chunks:0},this.promise=Promise.resolve()}request(e){const t=e.map(s=>s.file).sort().join("|");if(t===this.key)return this.promise;this.key=t,this.controller?.abort();const n=new AbortController;this.controller=n;const r=++this.generation;return this.status={ready:!1,pending:e.length,failed:0,generation:r,loaded_chunks:0},this.onStatus(this.status),this.promise=(async()=>{const s=new Map;try{let a=0;const o=async()=>{for(;a<e.length&&!n.signal.aborted;){const p=e[a++],y=this.cache.get(p.file)?.data||await this.fetchJson(p.file,!0,n.signal);if(n.signal.aborted||r!==this.generation)return;if(!Array.isArray(y?.primitives)||y.primitives.length!==p.count)throw new Error(`Invalid geometry chunk: ${p.file}`);this.cache.delete(p.file),this.cache.set(p.file,{data:y,bytes:p.bytes}),s.set(p.file,y.primitives),this.status.pending-=1,this.status.loaded_chunks+=1}};if(await Promise.all([o(),o()]),n.signal.aborted||r!==this.generation)return;const l=e.flatMap(p=>s.get(p.file)),c=new Set(l.map(p=>p.id)),h=this.overview.filter(p=>!c.has(p.id)).concat(l),u=new Set(e.map(p=>p.file));let f=[...this.cache.values()].reduce((p,_)=>p+_.bytes,0);for(const[p,_]of this.cache){if(f<=48*1024*1024)break;u.has(p)||(this.cache.delete(p),f-=_.bytes)}this.onCommit(h),this.status.ready=!0,this.onStatus(this.status)}catch(a){if(r!==this.generation||n.signal.aborted)return;n.abort(),this.status={...this.status,ready:!1,pending:0,failed:1,error:String(a)},this.onStatus(this.status)}})(),this.promise}dispose(){this.generation+=1,this.controller?.abort(),this.cache.clear()}}const fu=(i,e)=>Math.hypot(Math.max(i[0]-e.x,0,e.x-i[2]),Math.max(i[1]-e.y,0,e.y-i[3]));function lv(i,{profile:e,mode:t,buildingId:n,targets:r=[],kind:s,camera:a,focus:o,localRadius:l=180,screenMeasure:c}){if(e==="navigation")return[];if(e==="paper_capture"&&["overview","building","full"].includes(t))return i.chunks;if(c&&["interactive","presentation","snapshot"].includes(e)&&["overview","full","building"].includes(t))return i.chunks.filter(p=>{if(t==="building"&&p.scope_id===n)return!0;const _=c(p);return(_.visible||_.shadow)&&_.pixels>=.75});if(s==="global"&&t==="overview")return[];const h=new Set(r);["building","floor","floor_plan","room"].includes(t)&&n&&h.add(n);const u=i.chunks.filter(p=>h.has(p.scope_id)||p.owner_ids.some(_=>h.has(_))),f=new Set(u.map(p=>p.file));if(a.z<180&&["overview","full"].includes(t)){const p=i.chunks.map(g=>({c:g,d:Math.min(fu(g.bounds,a),fu(g.bounds,o))})).filter(({c:g,d:m})=>!f.has(g.file)&&m<l).sort((g,m)=>g.d-m.d||g.c.file.localeCompare(m.c.file)),_=new Set(u.filter(g=>g.scope==="building").map(g=>g.scope_id));let y=0;for(const{c:g}of p){if(g.scope==="building"){if(!_.has(g.scope_id)&&_.size>=3)continue;_.add(g.scope_id)}else{if(y+g.count>1e4)continue;y+=g.count}f.add(g.file)}for(const g of i.chunks)_.has(g.scope_id)&&g.scope==="building"&&f.add(g.file)}return i.chunks.filter(p=>f.has(p.file))}function cv(i,e,t,n={}){const r=new Set([...i,n.landscape_site].filter(Boolean));return[...e].some(s=>!["city","district"].includes(t.get(s)?.type)&&r.has(s))}function dv(i,e,t){if(Math.abs(i.rotation.x)>1e-8||Math.abs(i.rotation.y)>1e-8||i.matrixAutoUpdate===!1)return null;const n=[];let r=!1;if(i.updateMatrixWorld(!0),i.traverseVisible(a=>{(a.isSkinnedMesh||a.isInstancedMesh||a.morphTargetInfluences?.length)&&(r=!0),a.isMesh&&n.push(a)}),r||!n.length)return null;const s=i.matrixWorld.clone().invert();return n.map(a=>{const o=new bs(a.geometry,a.material,e.length),l=new De().multiplyMatrices(s,a.matrixWorld);return e.forEach((c,h)=>o.setMatrixAt(h,t(c).multiply(l))),o.instanceMatrix.needsUpdate=!0,o.computeBoundingSphere(),o.userData.entries=e,o.userData.citygAssetBatch=!0,o.castShadow=!0,o.receiveShadow=!0,o})}function uv(i,e){if(!e.length)return!1;if(i.function==="corridor"||i.metadata?.open_plan===!0||i.metadata?.space_kind==="open_plan")return!0;if(!i.bounds)return!1;const t=(r,s,a)=>e.some(o=>{const l=o.metadata||{};return l.wall_role==="room_view_cap"&&l.room_isolation_cap===!0&&l.wall_side===a?!0:typeof l.canonical_boundary=="number"&&Math.abs(l.canonical_boundary-r)<=.001&&(s?o.size.x>=o.size.y:o.size.y>=o.size.x)}),n=i.bounds;return t(n.min_y,!0,"south")&&t(n.max_y,!0,"north")&&t(n.min_x,!1,"west")&&t(n.max_x,!1,"east")}function _h(i,e){const{size:t,center:n,metadata:r={}}=i,s=r.hinge_local_m??(t.x>=t.y?[-t.x/2,0,0]:[0,-t.y/2,0]);if(s.length!==3||!s.every(Number.isFinite)||Math.abs(s[2])>1e-9||Math.abs(s[0])>t.x/2+1e-9||Math.abs(s[1])>t.y/2+1e-9)throw new Error("Invalid door hinge");const a=(i.rotation_z_deg||0)*Math.PI/180,o=a+e*Math.PI/180,l=n.x+Math.cos(a)*s[0]-Math.sin(a)*s[1],c=n.y+Math.sin(a)*s[0]+Math.cos(a)*s[1];return{x:l-Math.cos(o)*s[0]+Math.sin(o)*s[1],y:c-Math.sin(o)*s[0]-Math.cos(o)*s[1],z:n.z,angle:o}}function hv(i,e){if(!i)return null;const t=e.get(i.building_id),n=e.get(i.floor_id);if(t?.type!=="building"||n?.type!=="floor"||n.buildingId!==i.building_id)throw new Error("Hierarchy display requires a real building and one of its floors");const r=i.shell_opacity??.12;if(!Number.isFinite(r)||r<0||r>1)throw new Error("Invalid shell opacity");if(i.cut_above_m!=null&&!Number.isFinite(i.cut_above_m))throw new Error("Invalid cut elevation");return{building_id:i.building_id,floor_id:i.floor_id,shell_opacity:r,cut_above_m:i.cut_above_m??null}}function yh(i,e,t){return!!(i&&t==="building_shell"&&e?.buildingId===i.building_id)}function fv(i,e,t,n){return i?["roads","building_shell","district","root"].includes(t)?!0:e?.buildingId===i.building_id&&n:null}function pv(i,e,t=[0,0,0],n=0){const r=new De().makeRotationZ(n);r.setPosition(...t);const s=new Map([[i.root,r]]);for(const a of i.joints){const o=new De().fromArray(a.origin.flat()).transpose(),l=new De,c=e[a.name]??0;if(a.type==="prismatic"?l.makeTranslation(...a.axis.map(h=>h*c)):(a.type==="revolute"||a.type==="continuous")&&l.makeRotationAxis(new P(...a.axis).normalize(),c),!s.has(a.parent))throw new Error(`Unresolved robot joint ${a.name}`);s.set(a.child,s.get(a.parent).clone().multiply(o).multiply(l))}return s}async function mv(i,e){const t=await fetch(e,{cache:"no-store"});if(!t.ok)throw new Error("Robot mesh missing from portable package");const n=await t.arrayBuffer(),r=await crypto.subtle.digest("SHA-256",n);if([...new Uint8Array(r)].map(c=>c.toString(16).padStart(2,"0")).join("")!==i.glb_sha256)throw new Error("Robot mesh hash mismatch");const{scene:a}=await new ph().parseAsync(n,""),o=new Map;for(const c of Object.keys(i.links)){const h=a.getObjectByName(c);if(!h)throw new Error(`Robot mesh has no link ${c}`);h.matrixAutoUpdate=!1,o.set(c,h)}let l=0;return a.traverse(c=>{c.isMesh&&(l++,c.castShadow=!0,c.receiveShadow=!0)}),{scene:a,meshCount:l,linkCount:o.size,effectorPosition(){return a.updateMatrixWorld(!0),new P(...i.grasp_offset).applyMatrix4(o.get(i.end_effector_link).matrixWorld).toArray()},apply(c){for(const[h,u]of pv(i,c.robot_joints,c.robot_root,c.robot_yaw_deg*Math.PI/180))o.get(h).matrix.copy(u),o.get(h).matrixWorldNeedsUpdate=!0},dispose(){const c=new Set,h=new Set,u=new Set;a.traverse(f=>{if(f.isMesh){c.add(f.geometry);for(const p of Array.isArray(f.material)?f.material:[f.material])h.add(p)}});for(const f of h){for(const p of Object.values(f))p?.isTexture&&u.add(p);f.dispose()}for(const f of u)f.dispose();for(const f of c)f.dispose();a.removeFromParent()}}}function pu(i,e){let t=0,n=i.length-1;for(;t<n;){const r=Math.ceil((t+n)/2);i[r].time_s<=e?t=r:n=r-1}return i[t]}function gv(i){const e=document.createElement("section");e.hidden=!0,e.innerHTML=`<div class="section-label">Scripted task replay</div>
    <button class="button wide" data-load>Load A403 → B716</button>
    <div data-controls hidden><button class="button" data-play>Play</button>
    <button class="button" data-stop>Exit replay</button>
    <label class="field-label">Speed <select data-speed><option>1</option><option>5</option><option selected>20</option><option>50</option></select></label>
    <input data-seek type="range" min="0" max="1" step="0.05" value="0" style="width:100%" />
    <label><input data-follow type="checkbox" checked /> Follow robot / floor</label>
    <label class="field-label">Replay camera <select data-camera><option value="chase">Robot rear follow</option><option value="robot">Robot close-up (side)</option><option value="context">Route context</option></select></label>
    <label data-proxy-label hidden><input data-proxy type="checkbox" /> Debug occupancy proxy</label>
    <p data-status></p><small data-scope>Kinematic proxy replay · no learned policy or arm IK.</small></div>`,document.querySelector(".left-panel").prepend(e);const t=T=>e.querySelector(T),n=new At;i.scene.add(n);let r=null,s=!1,a=0,o=new Set,l=new Map,c=null,h=0,u=performance.now(),f=null;const p=new yi(1,1,1);function _(T,L,C=!1){if(!l.has(T)){const R=C?new ja(.5,.5,1,16):p;C&&R.rotateX(Math.PI/2);const v=new ut(R,new Dn({color:L,roughness:.65}));n.add(v),l.set(T,v)}return l.get(T)}function y(T,L,C,R=0,v=9215396,b=!1){const A=_(T,v,b);A.visible=!0,A.position.set(...L),A.scale.set(...C),A.rotation.set(0,0,R*Math.PI/180)}function g(){if(!r)return;const{task:T,trace:L}=r,C=pu(L.frames,a),R=C.robot_base;for(const A of l.values())A.visible=!1;if(c){if(c.apply(C),t("[data-proxy]").checked){y("robot",R,T.robot.size,C.robot_yaw_deg,3639759);const A=l.get("robot").material;A.wireframe=!0}}else y("robot",R,T.robot.size,C.robot_yaw_deg??T.robot.yaw,3639759),l.get("robot").material.wireframe=!1;y("payload",C.objects[T.object_id].position,T.object.size,T.object.yaw,15909976,!0);const v=C.objects[T.object_id].quaternion;v&&l.get("payload").quaternion.fromArray(v);const b=A=>Math.hypot(A[0]-R[0],A[1]-R[1])<35&&Math.abs(A[2]-R[2])<4;for(const[A,U]of Object.entries(T.doors)){const z={center:{x:U.box.center[0],y:U.box.center[1],z:U.box.center[2]},size:{x:U.box.size[0],y:U.box.size[1],z:U.box.size[2]},rotation_z_deg:U.box.yaw,metadata:{hinge_local_m:U.hinge}},B=_h(z,C.doors[A]);b([B.x,B.y,B.z])&&y(A,[B.x,B.y,B.z],U.box.size,B.angle*180/Math.PI,11896916)}for(const[A,U]of Object.entries(T.lifts)){const z=C.lifts[A],B=z.z-U.initial_floor_z;for(const V of U.cabin_parts){if(t("[data-follow]").checked&&V.id.includes("roof"))continue;const G=[V.center[0],V.center[1],V.center[2]+B];b(G)&&y(V.id,G,V.size,V.yaw)}for(const V of U.panels){const G=V.level_z===null||V.level_z===z.landing_z?z.opening:0,J=V.box.center.map((j,re)=>j+V.offset[re]*G+(re===2&&V.level_z===null?B:0));b(J)&&y(V.box.id,J,V.box.size,V.box.yaw)}}t("[data-follow]").checked&&(f=i.follow(R,f,{mode:t("[data-camera]").value,yaw:C.robot_yaw_deg??0})),t("[data-seek]").value=a,t("[data-status]").textContent=`${a.toFixed(1)} / ${L.frames.at(-1).time_s.toFixed(1)} s · ${C.action}`,i.draw()}function m(){h++,c?.dispose(),c=null,s=!1,r=null,o.clear(),n.visible=!1,f=null,t("[data-play]").textContent="Play",t("[data-controls]").hidden=!0,t("[data-load]").disabled=!1,i.rebuild()}async function E(){const T=++h,L=await fetch("./scene/task_replay.json",{cache:"no-store"});if(!L.ok)throw new Error("No task replay in this scene package");const C=await L.json(),R=await fetch("./scene/geometry_manifest.json",{cache:"no-store"});if(!R.ok)throw new Error("Scene manifest unavailable");const v=await crypto.subtle.digest("SHA-256",await R.arrayBuffer()),b=[...new Uint8Array(v)].map(U=>U.toString(16).padStart(2,"0")).join("");if(C.scene_sha256!==b||!C.acceptance?.ok)throw new Error("Stale or unaccepted task replay");if(!C.trace?.frames?.length)throw new Error("Empty task replay");let A=null;if(C.robot_model&&(A=await mv(C.robot_model,"./scene/robot_model.glb"),!C.trace.frames.every(U=>U.robot_root&&U.robot_joints)))throw A.dispose(),new Error("Missing articulated robot states");if(T!==h){A?.dispose();return}c?.dispose(),c=A,A&&n.add(A.scene),t("[data-proxy-label]").hidden=!A,t("[data-camera]").value=A?"chase":"context",t("[data-scope]").textContent=A?"Fetch · scripted drive + arm IK · sampled link collision checks · no grasp dynamics":"Kinematic proxy replay · no learned policy or arm IK.",r=C,s=!1,a=0,f=null,o=new Set(r.task.source_primitive_ids),t("[data-play]").textContent="Play";for(const U of Object.keys(r.task.doors))o.add(U);for(const U of Object.values(r.task.lifts)){for(const z of U.cabin_parts)o.add(z.id);for(const z of U.panels)o.add(z.box.id)}n.visible=!0,t("[data-controls]").hidden=!1,t("[data-load]").disabled=!0,t("[data-seek]").max=r.trace.frames.at(-1).time_s,i.begin?.(),i.rebuild(),g()}t("[data-load]").onclick=()=>E().catch(T=>i.error(T.message)),t("[data-play]").onclick=()=>{r&&(a>=r.trace.frames.at(-1).time_s&&(a=0),s=!s,t("[data-play]").textContent=s?"Pause":"Play")},t("[data-stop]").onclick=m,t("[data-proxy]").onchange=g,t("[data-camera]").onchange=g,t("[data-follow]").onchange=g,t("[data-seek]").oninput=()=>{a=Number(t("[data-seek]").value),g()};function w(T){r&&s&&(a=Math.min(r.trace.frames.at(-1).time_s,a+Math.min((T-u)/1e3,.1)*Number(t("[data-speed]").value)),g(),a>=r.trace.frames.at(-1).time_s&&(s=!1,t("[data-play]").textContent="Play")),u=T,requestAnimationFrame(w)}requestAnimationFrame(w);const x={load:E,exit:m,reset:m,available:T=>{e.hidden=!T},suppressed:T=>o.has(T),milestones:()=>r?Object.fromEntries(["attach","stow_object","door","transit:enter","transit:ride","place_object","release"].map(T=>[T,r.trace.frames.find(L=>L.action===T)?.time_s]).filter(([,T])=>T!==void 0)):{},seek:T=>{if(!r)throw new Error("Replay not loaded");a=Math.max(0,Math.min(T,r.trace.frames.at(-1).time_s)),g()},status:()=>({loaded:!!r,playing:s,seconds:a,suppressed_count:o.size,camera_mode:t("[data-camera]").value,following:t("[data-follow]").checked,camera:i.cameraState?.(),robot:c?{name:"Fetch",loaded:!0,links:c.linkCount,meshes:c.meshCount,effector_position:c.effectorPosition()}:null,frame:r?pu(r.trace.frames,a):null})};return window.citygTaskReplay=x,x}function _v(i,e=0,t="chase",n=!1){const r=e*Math.PI/180,s=Math.cos(r),a=Math.sin(r);return t==="chase"?{position:[i[0]-.8*s,i[1]-.8*a,i[2]+1.35],target:[i[0]+1.5*s,i[1]+1.5*a,i[2]+.35]}:t==="robot"?{position:[i[0]+2.4*s+2.4*a,i[1]+2.4*a-2.4*s,i[2]+2.2],target:[i[0]+.3*s,i[1]+.3*a,i[2]+.15]}:{position:[i[0]+(n?1.8:8),i[1]-(n?2.4:10),i[2]+(n?7:9)],target:[...i]}}function yv(i,e,t=2560,n=8192){if(![i,e,t,n].every(s=>Number.isFinite(s)&&s>0))throw new Error("Invalid screenshot dimensions");const r=Math.min(t/Math.max(i,e),n/Math.max(i,e),Math.sqrt(8388608/(i*e)));return{width:Math.max(1,Math.round(i*r)),height:Math.max(1,Math.round(e*r))}}function xv(i){return new Promise((e,t)=>i.toBlob(n=>n?e(n):t(new Error("PNG encoding failed; try a smaller output")),"image/png"))}function vv({camera:i,target:e,viewport:t,sceneRef:n,selection:r,visibility:s,lighting:a,replay:o=null,assetStatus:l=null,createdAt:c=new Date().toISOString()}){if(!i.isPerspectiveCamera)throw new Error("Render view export requires a perspective camera");if(![t.width,t.height,i.aspect].every(f=>Number.isFinite(f)&&f>0))throw new Error("Cannot export a hidden or zero-sized viewport");i.updateMatrixWorld(!0);const u={schema:"cityg.render_view",schema_version:1,created_at:c,coordinate_system:{space:"scene_world",up_axis:"Z",units:"meters",handedness:"right",camera_forward_local:[0,0,-1],camera_up_local:[0,1,0],matrix_layout:"column_major",quaternion_order:"xyzw"},scene_ref:n,camera:{projection:"perspective",camera_position:i.position.toArray(),look_at:e.toArray(),up:i.up.toArray(),quaternion_xyzw:i.quaternion.toArray(),matrix_world:i.matrixWorld.toArray(),projection_matrix:i.projectionMatrix.toArray(),vertical_fov_deg:i.getEffectiveFOV(),nominal_vertical_fov_deg:i.fov,zoom:i.zoom,aspect:i.aspect,near_clip_m:i.near,far_clip_m:i.far,film_gauge_mm:i.filmGauge,film_offset_mm:i.filmOffset,view_offset:i.view},viewport:{width_css_px:t.width,height_css_px:t.height,drawing_buffer_width_px:t.bufferWidth,drawing_buffer_height_px:t.bufferHeight},selection:r,visibility:s,lighting:a,replay:o,asset_status:l,render_contract:{preserve_aspect:!0,preserve_camera_orientation:!0,fov_convention:"vertical; effective FOV already includes zoom",scope:"Camera and display-state handoff, not a scene package or an automatic Cycles render",note:"Use the matching scene package. Do not replace the saved aspect with the output window aspect."}};return JSON.parse(JSON.stringify(u))}function Mv(i){const e=r=>String(r||"scene").replace(/[^a-zA-Z0-9_-]/g,"_").slice(0,100),t=i.visibility.mode,n={room:i.selection.room_id,floor:i.selection.floor_id,building:i.selection.building_id,district:i.selection.district_id}[t]||t;return`${e(i.scene_ref.city_id)}_${e(n)}_${e(i.created_at)}_render_view.json`}function bv(){const i=new ut(new yt,new Dn({color:10857890,roughness:1,fog:!1})),e={start:{value:800},end:{value:2400},color:{value:new Ee}};i.userData.haze=e,i.material.onBeforeCompile=n=>{Object.assign(n.uniforms,{citygHorizonStart:e.start,citygHorizonEnd:e.end,citygHorizonColor:e.color}),n.vertexShader=`varying vec3 vCitygHorizonWorld;
`+n.vertexShader.replace("#include <worldpos_vertex>",`#include <worldpos_vertex>
vCitygHorizonWorld=(modelMatrix*vec4(transformed,1.0)).xyz;`),n.fragmentShader=`varying vec3 vCitygHorizonWorld;
uniform float citygHorizonStart;
uniform float citygHorizonEnd;
uniform vec3 citygHorizonColor;
`+n.fragmentShader.replace("#include <opaque_fragment>",`
float horizonDistance=length(vCitygHorizonWorld.xy-cameraPosition.xy);
float horizonHaze=smoothstep(citygHorizonStart,citygHorizonEnd,horizonDistance);
outgoingLight=mix(outgoingLight,citygHorizonColor,horizonHaze);
#include <opaque_fragment>`)},i.material.customProgramCacheKey=()=>"opaque-horizontal-horizon-v1",i.visible=!1,i.receiveShadow=!0;const t=new ut(new Ss(2,2),new ti({transparent:!0,depthTest:!0,depthWrite:!1,uniforms:{hazeColor:e.color,inverseProjection:{value:new De},cameraWorld:{value:new De},aboveGround:{value:1}},vertexShader:`varying vec2 skyNdc;
void main() { skyNdc=position.xy; gl_Position=vec4(position.xy,1.0,1.0); }`,fragmentShader:`varying vec2 skyNdc;
uniform mat4 inverseProjection;
uniform mat4 cameraWorld;
uniform vec3 hazeColor;
uniform float aboveGround;
void main() {
  vec4 viewRay=inverseProjection*vec4(skyNdc,1.0,1.0);
  vec3 worldRay=normalize((cameraWorld*vec4(viewRay.xyz,0.0)).xyz);
  // About four degrees of atmospheric transition above the true horizon,
  // retaining the original HDR everywhere else (no sharp backdrop seam).
  float veil=1.0-smoothstep(0.0,0.07,worldRay.z);
  if (veil<=0.0 || aboveGround<0.5) discard;
  gl_FragColor=vec4(hazeColor,veil);
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}`}));return t.renderOrder=-1e3,t.frustumCulled=!1,t.onBeforeRender=(n,r,s)=>{t.material.uniforms.inverseProjection.value.copy(s.projectionMatrixInverse),t.material.uniforms.cameraWorld.value.copy(s.matrixWorld),t.material.uniforms.aboveGround.value=s.matrixWorld.elements[14]>=i.position.z?1:0},i.add(t),i}function Sv(i,e,t,n,r,s){i.material.color.setRGB(...t?.display_color||[.4,.45,.4]),i.material.roughness=t?.roughness??1,i.material.metalness=t?.metallic??0;const a=i.userData.haze;a.start.value=Math.max(400,n*.8),a.end.value=Math.max(1200,n*2.5),a.color.value.setRGB(...r).multiplyScalar(s),i.position.set(e.center.x,e.center.y,e.center.z+e.size.z/2-.025);const o=Math.max(1e4,n*40),l=`${e.size.x},${e.size.y},${o}`;i.userData.key!==l&&(i.geometry.dispose(),i.geometry=wv(e.size.x,e.size.y,o),i.userData.key=l),i.rotation.z=(e.rotation_z_deg||0)*Math.PI/180,i.visible=!0}function wv(i,e,t){const n=i/2,r=e/2,s=t,a=[[-n-s,-r-s,-n,r+s],[n,-r-s,n+s,r+s],[-n,-r-s,n,-r],[-n,r,n,r+s]],o=[],l=[];for(const[h,u,f,p]of a){const _=o.length/3;o.push(h,u,0,f,u,0,f,p,0,h,p,0),l.push(_,_+1,_+2,_,_+2,_+3)}const c=new yt;return c.setAttribute("position",new mt(o,3)),c.setIndex(l),c.computeVertexNormals(),c}function Ev(i,e,t,n,r){return e&&!["floor","floor_plan","room"].includes(i)&&t.environment&&n!=="none"&&!!r?.[n]}function mu(i,e,t,n){const r=((i+.5)/t-.5)*Math.PI*2,s=(.5-(e+.5)/n)*Math.PI;return new P(Math.cos(s)*Math.cos(r),-Math.cos(s)*Math.sin(r),Math.sin(s))}function Tv(i){const{data:e,width:t,height:n}=i.image,r=e.length/(t*n),s=h=>i.type===In?ns.fromHalfFloat(e[h]):e[h];let a=-1,o=mu(t/2,n/4,t,n);for(let h=0;h<n*.48;h+=2)for(let u=0;u<t;u+=2){const f=(h*t+u)*r,p=s(f)*.2126+s(f+1)*.7152+s(f+2)*.0722;p>a&&(a=p,o=mu(u,h,t,n))}const l=[0,0,0];let c=0;for(let h=Math.floor(n*.46);h<n*.49;h+=4)for(let u=0;u<t;u+=16){const f=(h*t+u)*r;for(let p=0;p<3;p++)l[p]+=s(f+p);c++}return{sun:o,horizon:l.map(h=>h/Math.max(1,c))}}function Av(i,e=215,t=0){const n=(e+t)*Math.PI/180-Math.atan2(i.sun.y,i.sun.x);return{rotation:new pn(Math.PI/2,0,n,"XYZ"),sun:i.sun.clone().applyAxisAngle(new P(0,0,1),n)}}function Rv(i,e){const t=new Map;for(const r of i){if(r.semantic_class!=="floor_slab")continue;const s=e.get(r.owner_id),a=r.metadata?.building_id||s?.buildingId,o=s?.type==="floor"?s.entity:null;!a||(o?o.level!==0:Math.abs(r.center.z)>.3)||(t.has(a)||t.set(a,[]),t.get(a).push(r))}const n=new Map;for(const[r,s]of t){const a=[];for(const o of s){const l=(o.rotation_z_deg||0)*Math.PI/180,c=Math.cos(l),h=Math.sin(l),u=f=>[o.center.x+c*f[0]*o.size.x-h*f[1]*o.size.y,o.center.y+h*f[0]*o.size.x+c*f[1]*o.size.y];if(o.primitive_type==="box"){const f=[[-.5,-.5],[.5,-.5],[.5,.5],[-.5,.5]].map(u);f.forEach((p,_)=>a.push([...p,...f[(_+1)%4]]))}else if(o.primitive_type==="path_mesh"){const f=o.metadata?.mesh_vertices||[],p=new Map,_=Math.max(...f.map(y=>y[2]));for(const y of o.metadata?.mesh_triangles||[])if(y.every(g=>Math.abs(f[g][2]-_)<1e-5))for(let g=0;g<3;g++){const m=y[g],E=y[(g+1)%3],w=[m,E].sort((T,L)=>T-L).join(","),x=p.get(w)||{u:m,v:E,count:0};x.count++,p.set(w,x)}for(const{u:y,v:g,count:m}of p.values())m===1&&a.push([...u(f[y]),...u(f[g])])}}n.set(r,a)}return n}function Cv(i,e="",t=new Map){const n=i?.bounds;if(!n||![n.min_x,n.min_y,n.max_x,n.max_y].every(Number.isFinite))return null;const r=(i.buildings||[]).filter(o=>o.footprint).slice(0,8),s=e.includes("lawn");let a=0;for(const o of String(i.id))a=Math.imul(a,31)+o.charCodeAt(0)>>>0;return{green:s,seed:a%1e4/37,bounds:[n.min_x,n.min_y,n.max_x,n.max_y],edges:r.flatMap(o=>t.get(o.id)||[]).slice(0,64),buildings:r.map(o=>{const l=o.footprint,c=(l.min_x+l.max_x)/2,h=(l.min_y+l.max_y)/2,u=Number(o.metadata?.orientation_deg||0)*Math.PI/180,f=o.entrance||{x:c,y:l.min_y},p=f.x-c,_=f.y-h;return{box:[c,h,(l.max_x-l.min_x)/2,(l.max_y-l.min_y)/2],pose:[Math.cos(u),Math.sin(u),0,0],entrance:[c+p*Math.cos(u)-_*Math.sin(u),h+p*Math.sin(u)+_*Math.cos(u),0,0]}})}}const Pv=`
varying vec2 uwGroundXY;
uniform vec4 uwParcel;
uniform vec4 uwBuildings[8];
uniform vec4 uwPoses[8];
uniform vec4 uwEntrances[8];
uniform vec4 uwEdges[64];
uniform int uwEdgeCount;
uniform int uwBuildingCount;
uniform float uwGreenBase, uwSeed, uwStrength, uwOtherReady, uwOtherScale;
uniform sampler2D uwOtherColor, uwOtherNormal, uwOtherRoughness;
uniform vec2 uwOtherChannels;
float uwHash(vec2 p) { return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
float uwNoise(vec2 p) {
  vec2 i=floor(p),f=fract(p); f=f*f*(3.0-2.0*f);
  return mix(mix(uwHash(i),uwHash(i+vec2(1,0)),f.x),
             mix(uwHash(i+vec2(0,1)),uwHash(i+vec2(1,1)),f.x),f.y);
}
float uwHardscape(vec2 p) {
  float apron=0.0,entry=0.0;
  for (int i=0;i<64;i++) {
    if(i>=uwEdgeCount) break;
    vec2 a=uwEdges[i].xy,b=uwEdges[i].zw,ab=b-a;
    float t=clamp(dot(p-a,ab)/max(dot(ab,ab),0.0001),0.0,1.0);
    float d=length(p-a-t*ab);
    apron=max(apron,1.0-smoothstep(1.3,1.6,d));
  }
  for (int i=0;i<8;i++) {
    if (i>=uwBuildingCount) break;
    vec4 b=uwBuildings[i];vec2 cs=uwPoses[i].xy;
    vec2 outward=uwEntrances[i].xy-b.xy;
    outward/=max(length(outward),0.001);
    vec2 rel=p-uwEntrances[i].xy;
    float along=dot(rel,outward),across=abs(dot(rel,vec2(-outward.y,outward.x)));
    // A forecourt, not a claimed navigable connection to a road. Existing
    // compiled access paths remain above this material and are untouched.
    entry=max(entry,(1.0-smoothstep(6.0,6.3,across))*
      (1.0-smoothstep(9.0,9.3,along))*smoothstep(-2.0,-1.7,along));
  }
  vec2 edge=min(p-uwParcel.xy,uwParcel.zw-p);
  float border=min(edge.x,edge.y);
  float plantedWidth=3.5+1.2*uwNoise(p/12.0+uwSeed);
  float greenEdge=1.0-smoothstep(plantedWidth-0.15,plantedWidth+0.15,border);
  float hard=mix(1.0-greenEdge,0.0,uwGreenBase);
  return max(hard,max(apron,entry));
}
`;function Iv(i,e,{strength:t=1,otherScale:n=4}={}){const r={uwParcel:{value:new Ye(...e.bounds)},uwSeed:{value:e.seed},uwGreenBase:{value:e.green?1:0},uwStrength:{value:Math.max(0,Math.min(1.5,t))},uwBuildingCount:{value:e.buildings.length},uwEdgeCount:{value:e.edges.length},uwEdges:{value:Array.from({length:64},(s,a)=>new Ye(...e.edges[a]||[0,0,0,0]))},uwBuildings:{value:Array.from({length:8},(s,a)=>new Ye(...e.buildings[a]?.box||[0,0,0,0]))},uwPoses:{value:Array.from({length:8},(s,a)=>new Ye(...e.buildings[a]?.pose||[1,0,0,0]))},uwEntrances:{value:Array.from({length:8},(s,a)=>new Ye(...e.buildings[a]?.entrance||[0,0,0,0]))},uwOtherColor:{value:null},uwOtherNormal:{value:null},uwOtherRoughness:{value:null},uwOtherReady:{value:0},uwOtherScale:{value:n},uwOtherChannels:{value:new xe(0,0)}};return i.onBeforeCompile=s=>{Object.assign(s.uniforms,r),s.vertexShader=`varying vec2 uwGroundXY;
`+s.vertexShader,s.vertexShader=s.vertexShader.replace("#include <project_vertex>",`#include <project_vertex>
      vec4 uwWorld=vec4(transformed,1.0);
      #ifdef USE_INSTANCING
        uwWorld=instanceMatrix*uwWorld;
      #endif
      uwGroundXY=(modelMatrix*uwWorld).xy;`),s.fragmentShader=Pv+s.fragmentShader,s.fragmentShader=s.fragmentShader.replace("#include <map_fragment>",`#include <map_fragment>
      float uwHard=uwHardscape(uwGroundXY);
      float uwMix=uwOtherReady*mix(1.0-uwHard,uwHard,uwGreenBase);
      vec2 uwUV=uwGroundXY/uwOtherScale;
      diffuseColor.rgb=mix(diffuseColor.rgb,texture2D(uwOtherColor,uwUV).rgb,uwMix);
      // The installed grass scan contains dry yellow blades. Use a restrained
      // maintained-lawn tint for BOTH samplers, instead of inheriting whichever
      // semantic green/grey happened to be on the original whole-parcel base.
      float uwActualHard=mix(1.0-uwGreenBase,uwHard,uwOtherReady);
      diffuseColor.rgb*=mix(vec3(0.32,0.48,0.23),vec3(0.80,0.78,0.73),uwActualHard);
      float uwBroad=uwNoise(uwGroundXY/24.0+uwSeed);
      float uwMedium=uwNoise(uwGroundXY/7.0+uwSeed);
      vec3 uwGrassTint=mix(vec3(0.67,0.78,0.57),vec3(1.18,1.09,0.82),uwBroad);
      uwGrassTint*=0.88+0.22*uwMedium;
      // Meter-scale PBR alone averages to flat grey in aerial views. A separate
      // broad field supplies paving wear without enlarging joints/grain or
      // changing the established grass treatment and hardscape boundaries.
      float uwPavingField=uwNoise(uwGroundXY/32.0+uwSeed+vec2(19.3,7.1));
      float uwPavingTone=smoothstep(0.18,0.82,uwPavingField);
      float uwWear=0.60+0.68*uwPavingTone+0.10*uwMedium;
      vec3 uwPavingTint=mix(vec3(0.90,0.96,1.04),vec3(1.06,1.015,0.94),uwPavingTone)*uwWear;
      vec3 uwTint=mix(uwGrassTint,uwPavingTint,uwHard);
      diffuseColor.rgb*=mix(vec3(1.0),uwTint,uwStrength);
      float uwDry=smoothstep(0.56,0.85,uwBroad)*0.22*(1.0-uwHard)*uwStrength;
      diffuseColor.rgb=mix(diffuseColor.rgb,vec3(0.24,0.18,0.075),uwDry);
    `),s.fragmentShader=s.fragmentShader.replace("#include <roughnessmap_fragment>",`#include <roughnessmap_fragment>
      if (uwOtherChannels.y>0.5) roughnessFactor=mix(roughnessFactor,
        roughness*texture2D(uwOtherRoughness,uwUV).g,uwMix);
      roughnessFactor=clamp(roughnessFactor+(uwBroad-0.5)*0.09*uwStrength,0.3,1.0);`),s.fragmentShader=s.fragmentShader.replace("#include <normal_fragment_maps>",`#include <normal_fragment_maps>
      #ifdef USE_NORMALMAP_TANGENTSPACE
        if (uwOtherChannels.x>0.5) {
          vec3 uwN=texture2D(uwOtherNormal,uwUV).xyz*2.0-1.0;
          uwN.xy*=normalScale;
          normal=normalize(mix(normal,normalize(tbn*uwN),uwMix));
        }
      #endif
    `)},i.customProgramCacheKey=()=>"cityg-parcel-ground-v3",(s,a)=>{s==="base_color"&&(r.uwOtherColor.value=a,r.uwOtherReady.value=1),s==="normal"&&(r.uwOtherNormal.value=a,r.uwOtherChannels.value.x=1),s==="roughness"&&(r.uwOtherRoughness.value=a,r.uwOtherChannels.value.y=1)}}function Lv(i){const e=i?.centerline||[],t=[];for(let n=1;n<e.length;n++){const r=e[n-1],s=e[n],a=s.x-r.x,o=s.y-r.y,l=Math.hypot(a,o);[r.x,r.y,s.x,s.y,l].every(Number.isFinite)&&l>1e-6&&t.push({x:r.x,y:r.y,dx:a,dy:o,length:l})}return t}function Dv(i,e,t,n){let r=1/0,s=0,a=1;for(const o of i){const l=Math.max(0,Math.min(1,((e-o.x)*o.dx+(t-o.y)*o.dy)/(o.length*o.length))),c=(e-o.x-l*o.dx)**2+(t-o.y-l*o.dy)**2;c<r&&(r=c,s=o.dx/o.length,a=o.dy/o.length)}return[s,a,Math.min(1,Math.sqrt(r)/n)]}function Nv(i,e=512){const t=Lv(i),n=Number(i?.width_m)/2;if(!t.length||!Number.isFinite(n)||n<=0)return null;const r=t.flatMap(_=>[[_.x,_.y],[_.x+_.dx,_.y+_.dy]]),s=Math.min(...r.map(_=>_[0]))-n-2,a=Math.min(...r.map(_=>_[1]))-n-2,o=Math.max(...r.map(_=>_[0]))+n+2-s,l=Math.max(...r.map(_=>_[1]))+n+2-a,c=Math.max(32,Math.min(1024,Math.floor(e))),h=Math.max(32,Math.ceil(c*o/Math.max(o,l))),u=Math.max(32,Math.ceil(c*l/Math.max(o,l))),f=new Uint8Array(h*u*4);for(let _=0;_<u;_++)for(let y=0;y<h;y++){const[g,m,E]=Dv(t,s+(y+.5)*o/h,a+(_+.5)*l/u,n),w=(_*h+y)*4;f[w]=Math.round((g*.5+.5)*255),f[w+1]=Math.round((m*.5+.5)*255),f[w+2]=Math.round(E*255),f[w+3]=255}const p=new Wa(f,h,u,sn,Sn);return p.minFilter=p.magFilter=Tt,p.generateMipmaps=!1,p.needsUpdate=!0,{texture:p,bounds:new Ye(s,a,o,l)}}const Uv=`
varying vec2 uwWaterXY;
uniform sampler2D uwRiverField;
uniform vec4 uwRiverBounds;
uniform float uwWaterStrength;
float uwWaterHash(vec2 p){return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453);}
float uwWaterNoise(vec2 p){
  vec2 i=floor(p),f=fract(p);f=f*f*(3.0-2.0*f);
  return mix(mix(uwWaterHash(i),uwWaterHash(i+vec2(1,0)),f.x),
    mix(uwWaterHash(i+vec2(0,1)),uwWaterHash(i+vec2(1,1)),f.x),f.y);
}
vec3 uwRiverAt(vec2 p){return texture2D(uwRiverField,(p-uwRiverBounds.xy)/uwRiverBounds.zw).rgb;}
vec2 uwRipple(vec2 p,vec2 direction,float k,float slope,float phase){
  float warp=uwWaterNoise(p/3.0+vec2(phase,phase*1.7));
  float a=dot(p,direction)*k+phase+warp*5.0;
  // Do not replace subpixel waves with shimmering moire at city scale.
  float visible=1.0-smoothstep(0.6,2.8,fwidth(a));
  return direction*(cos(a)*slope*visible*(.45+.55*warp));
}
`;function Fv(i,e,{strength:t=1}={}){const n=Nv(e);if(!n)return!1;const r=Number.isFinite(t)?Math.max(0,Math.min(1.5,t)):1,s={uwRiverField:{value:n.texture},uwRiverBounds:{value:n.bounds},uwWaterStrength:{value:r}};return i.onBeforeCompile=a=>{Object.assign(a.uniforms,s),a.vertexShader=`varying vec2 uwWaterXY;
`+a.vertexShader,a.vertexShader=a.vertexShader.replace("#include <project_vertex>",`#include <project_vertex>
      vec4 uwWaterWorld=vec4(transformed,1.0);
      #ifdef USE_INSTANCING
        uwWaterWorld=instanceMatrix*uwWaterWorld;
      #endif
      uwWaterXY=(modelMatrix*uwWaterWorld).xy;`),a.fragmentShader=Uv+a.fragmentShader,a.fragmentShader=a.fragmentShader.replace("#include <map_fragment>",`#include <map_fragment>
      vec3 uwRiver=uwRiverAt(uwWaterXY);
      vec2 uwFlow=uwRiver.rg*2.0-1.0;uwFlow/=max(length(uwFlow),0.01);
      vec2 uwCross=vec2(-uwFlow.y,uwFlow.x);
      float uwShallow=smoothstep(0.58,1.0,uwRiver.b);
      float uwCloud=uwWaterNoise(uwWaterXY/22.0);
      // Turbid urban river: depth-colour approximation, not transparent ocean.
      vec3 uwColour=mix(vec3(.025,.105,.125),vec3(.095,.19,.155),uwShallow);
      uwColour*=.88+.24*uwCloud;
      float uwStreak=uwWaterNoise(vec2(dot(uwWaterXY,uwCross)/2.8,dot(uwWaterXY,uwFlow)/24.0));
      uwColour*=.94+.12*uwStreak;
      // Sparse near-bank disturbance, never a continuous white foam border.
      float uwEdge=smoothstep(.94,1.0,uwRiver.b)*smoothstep(.68,.88,uwWaterNoise(uwWaterXY/3.0));
      uwColour=mix(uwColour,vec3(.24,.30,.24),uwEdge*.20);
      diffuseColor.rgb=mix(diffuseColor.rgb,uwColour,clamp(uwWaterStrength,0.0,1.0));`),a.fragmentShader=a.fragmentShader.replace("#include <normal_fragment_maps>",`#include <normal_fragment_maps>
      vec2 uwSlope=uwRipple(uwWaterXY,uwFlow,.9,.012,1.2)
        +uwRipple(uwWaterXY,normalize(uwFlow+uwCross*.4),6.7,.035,2.7)
        +uwRipple(uwWaterXY,normalize(uwFlow-uwCross*.3),17.3,.04,.3);
      if(dot(normal,mat3(viewMatrix)*vec3(0,0,1))>.5)
        normal=normalize(mat3(viewMatrix)*vec3(-uwSlope*uwWaterStrength,1.0));`),a.fragmentShader=a.fragmentShader.replace("#include <clearcoat_normal_fragment_maps>",`#include <clearcoat_normal_fragment_maps>
      #ifdef USE_CLEARCOAT
        clearcoatNormal=normal;
      #endif`),a.fragmentShader=a.fragmentShader.replace("#include <roughnessmap_fragment>",`#include <roughnessmap_fragment>
      roughnessFactor=mix(roughnessFactor,.30+.09*uwShallow+.045*uwCloud,clamp(uwWaterStrength,0.0,1.0));`)},i.customProgramCacheKey=()=>"cityg-river-surface-v1",i.addEventListener("dispose",()=>n.texture.dispose()),i.userData.riverSurface=!0,!0}function Ov(i,e,t,n){if(!["overview","full","building"].includes(n))return null;const r=Math.hypot(i.x-e.x,i.y-e.y,i.z-e.z),s=Math.max(0,i.z-t);return Math.max(.03,Math.min(64,r/50,s/8))}function Bv(i,e,t){if(i.ready.has(e)){t(i.ready.get(e));return}i.promises.has(e)||(i.states.set(e,"pending"),i.promises.set(e,i.load(e).then(n=>(i.ready.set(e,n),i.owned.add(n),i.states.set(e,"loaded"),n),n=>{throw i.states.set(e,"failed"),n}))),i.promises.get(e).then(t).catch(()=>{})}function zv(i,e){i?.map&&!e.has(i.map)&&i.map.dispose()}function gc(i){i.traverse(e=>{e.isInstancedMesh&&e.dispose()})}function Wo(i){const e=new Set,t=new Set,n=new Set,r=new Set;i.traverse(s=>{s.geometry&&e.add(s.geometry);for(const a of[s.material].flat().filter(Boolean))t.add(a)});for(const s of t)for(const a of Object.values(s))a?.isTexture&&n.add(a);gc(i);for(const s of e)s.dispose();for(const s of t)s.dispose();for(const s of n)s.dispose(),s.source?.data&&r.add(s.source.data);for(const s of r)s.close?.()}function kv(i){const e=new Set,t=new Set;let n=0;return i.traverse(r=>{for(const s of[...Object.values(r.geometry?.attributes||{}),r.geometry?.index]){const a=(s?.array||s?.data?.array)?.buffer;a&&!e.has(a)&&(e.add(a),n+=a.byteLength)}for(const s of[r.material].flat().filter(Boolean))for(const a of Object.values(s)){if(!a?.isTexture||t.has(a.source))continue;t.add(a.source);const o=a.source?.data;n+=(o?.width||0)*(o?.height||0)*4*4/3}}),n}class Hv{constructor(e,{concurrency:t=3,idleBytes:n=64*1024*1024}={}){this.load=e,this.concurrency=t,this.idleBytes=n,this.entries=new Map,this.active=new Set,this.queue=[],this.running=0}retain(e){this.active=new Set(e),this.trim()}get(e){let t=this.entries.get(e);return t?(this.entries.delete(e),this.entries.set(e,t),t.promise):(t={root:null,bytes:0},t.promise=new Promise((n,r)=>{t.resolve=n,t.reject=r}),this.entries.set(e,t),this.queue.push([e,t]),this.pump(),t.promise)}pump(){for(;this.running<this.concurrency&&this.queue.length;){const[e,t]=this.queue.shift();if(this.entries.get(e)!==t||!this.active.has(e)){this.entries.get(e)===t&&this.entries.delete(e),t.reject(new Error("Obsolete asset request"));continue}this.running++,Promise.resolve().then(()=>this.load(e)).then(n=>{if(this.entries.get(e)!==t){Wo(n),t.reject(new Error("Obsolete asset cache"));return}t.root=n,t.bytes=kv(n),t.resolve(n)},n=>{this.entries.get(e)===t&&this.entries.delete(e),t.reject(n)}).finally(()=>{this.running--,this.trim(),this.pump()})}}trim(){let e=[...this.entries].reduce((t,[n,r])=>t+(this.active.has(n)?0:r.bytes),0);for(const[t,n]of this.entries){if(e<=this.idleBytes)break;n.root&&!this.active.has(t)&&(this.entries.delete(t),e-=n.bytes,Wo(n.root))}}clear(){this.active.clear();for(const e of this.entries.values())e.root&&Wo(e.root);this.entries.clear(),this.pump()}stats(){return{templates:this.entries.size,loading:this.running,queued:this.queue.length,estimated_template_bytes:[...this.entries.values()].reduce((e,t)=>e+t.bytes,0)}}}async function Gv(i,e,t,n=3){let r=0;await Promise.all(Array.from({length:n},async()=>{for(;r<i.length&&t();)await e(i[r++]),await new Promise(s=>setTimeout(s,0))}))}function xh(i,e,t){return Math.min(t,Math.sqrt(3e6/Math.max(1,i*e)))}function Vv(i){return i.pending===0&&(i.ready||i.failed>0)&&!i.gpu?.context_lost}function Wv(i){return i<=128?256:i<=512?1024:0}async function Xv(i,e,t){if(!e)return i;const n=new Set,r=new Map;i.traverse(a=>{for(const o of[a.material].flat().filter(Boolean))for(const l of Object.values(o))l?.isTexture&&n.add(l)});for(const a of n){const o=a.source?.data;if(!(!o||o.data||Array.isArray(o)||a.isCompressedTexture||Math.max(o.width||0,o.height||0)<=e)&&!r.has(o)){const l=e/Math.max(o.width,o.height);r.set(o,await t(o,Math.max(1,Math.round(o.width*l)),Math.max(1,Math.round(o.height*l))))}}const s=new Map([...n].map(a=>[a,a.source?.data]));for(const a of n){const o=r.get(s.get(a));o&&(a.image=o,a.needsUpdate=!0)}for(const a of r.keys())a.close?.();return i}const fn=i=>["interactive","presentation","snapshot"].includes(i);function gu(i){const e=(i.rotation_z_deg||0)*Math.PI/180,t=(Math.abs(Math.cos(e))*i.size.x+Math.abs(Math.sin(e))*i.size.y)/2,n=(Math.abs(Math.sin(e))*i.size.x+Math.abs(Math.cos(e))*i.size.y)/2;return new kt(new P(i.center.x-t,i.center.y-n,i.center.z-i.size.z/2),new P(i.center.x+t,i.center.y+n,i.center.z+i.size.z/2))}function jv(i){if(i.bounds3d)return new kt(new P(...i.bounds3d.slice(0,3)),new P(...i.bounds3d.slice(3)));const[e,t,n,r]=i.bounds;return new kt(new P(e,t,-100),new P(n,r,1e3))}function qv(i,e,t=[-250,-180,420]){i.updateMatrixWorld();const n=i.matrixWorldInverse.clone(),r=new Xa().setFromProjectionMatrix(new De().multiplyMatrices(i.projectionMatrix,n)),s=e*i.projectionMatrix.elements[5]/2,a=o=>{const l=o.getSize(new P).length()/2,c=-o.getCenter(new P).applyMatrix4(n).z;return c-l<=i.near?1/0:2*l*s/(c-l)};return{height:e,measure(o){const l=r.intersectsBox(o);let c=!1,h=0;if(!l&&t[2]>0&&o.max.z>0){const u=o.clone(),f=Math.max(0,o.max.z),p=new P(-t[0]*f/t[2],-t[1]*f/t[2],-f);u.union(o.clone().translate(p)),c=r.intersectsBox(u),c&&(h=a(u))}return{visible:l,shadow:c,pixels:l?a(o):h}}}}function Yv(i,e,t={}){return[...t[i]||[]].sort((r,s)=>r.max_pixels-s.max_pixels).find(r=>e<=r.max_pixels)?.asset_id||i}function vh(i,e=40){return`${Math.floor(i.center.x/e)},${Math.floor(i.center.y/e)}`}function _u(i,e){const t=Math.max(1,i.position.distanceTo(i.target.position));i.position.copy(i.target.position).addScaledVector(e.clone().normalize(),t)}function Kv(i,e){if(e.isEmpty())return;const t=i.position.clone().sub(i.target.position).normalize();if(t.z<=0)return;const n=e.clone(),r=Math.max(0,e.max.z);n.union(e.clone().translate(new P(-t.x*r/t.z,-t.y*r/t.z,-r)));const s=n.getCenter(new P),a=Math.max(5,n.getSize(new P).length()/2);i.target.position.copy(s),i.position.copy(s).addScaledVector(t,a*2+10),i.updateMatrixWorld(),i.target.updateMatrixWorld();const o=i.shadow.camera;o.position.copy(i.position),o.lookAt(s),o.updateMatrixWorld();const l=n.clone().applyMatrix4(o.matrixWorldInverse),c=Math.max(1,a*.03);o.left=l.min.x-c,o.right=l.max.x+c,o.bottom=l.min.y-c,o.top=l.max.y+c,o.near=Math.max(.1,-l.max.z-c),o.far=-l.min.z+c,o.updateProjectionMatrix()}function Mh(i){return!!(i.metadata?.resolved_asset&&i.metadata?.asset_id)&&!String(i.metadata.asset_id).startsWith("facade_")}function $v(i,e,t,n=64){const r=new Map,s=i.filter(Mh),a=c=>Math.hypot(c.center.x-e.x,c.center.y-e.y);for(const c of[...s].sort((h,u)=>t==="global"?String(h.id).localeCompare(String(u.id)):a(h)-a(u)||String(h.id).localeCompare(String(u.id)))){const h=t==="global"?`${Math.floor(c.center.x/100)}:${Math.floor(c.center.y/100)}`:c.metadata.asset_category||c.semantic_class;r.has(h)||r.set(h,[]),r.get(h).push(c)}const o=new Set,l=[...r.values()];for(let c=0;o.size<n;c++){let h=!1;for(const u of l)c<u.length&&o.size<n&&(o.add(u[c].id),h=!0);if(!h)break}return o}const za=["geometry_manifest.json","city.json"],Fl=["navigation.json","interactions.json","activation_manifest.json","validation_report.json","geometry_validation_report.json","interaction_smoke_report.json","usd_validation_report.json","compile_metrics.json"],Zv=7e3,Bt=Object.freeze({snapshot:{pixelRatio:()=>1,shadows:!0,materialTextures:!0,environment:!0,physicalGlass:!0},paper_capture:{pixelRatio:()=>1,shadows:!1,materialTextures:!0,environment:!1,physicalGlass:!1},prototype_capture:{pixelRatio:()=>1,shadows:!1,materialTextures:!0,environment:!1,physicalGlass:!1},interactive:{pixelRatio:()=>Math.min(window.devicePixelRatio||1,1.5),shadows:!0,materialTextures:!0,environment:!0,physicalGlass:!0},review:{pixelRatio:()=>1,shadows:!1,materialTextures:!1,environment:!1,physicalGlass:!1},navigation:{pixelRatio:()=>Math.min(window.devicePixelRatio||1,.72),shadows:!1,materialTextures:!1,environment:!1,physicalGlass:!1},presentation:{pixelRatio:()=>Math.min(window.devicePixelRatio||1,2),shadows:!0,materialTextures:!0,environment:!0,physicalGlass:!0},high_fidelity:{pixelRatio:()=>Math.min(window.devicePixelRatio||1,1.35),shadows:!1,materialTextures:!0,environment:!1,physicalGlass:!0}}),Pr={river_water:2654104,river_bed:4344887,river_bank:8425585,river_promenade:11315093,riparian_green:6718798,bridge_deck:8949394,bridge_parapet:10528420,bridge_railing:4940904,bridge_abutment:7830908,road_surface:4150105,road_median:9080711,bicycle_lane_surface:5405811,median_planter:7230519,median_shrub:5212747,stop_line:16117968,traffic_signal:2437433,traffic_signal_red:14240829,traffic_signal_green:4831353,road_marking:15984562,curb:10331555,lane_marking:15984562,crosswalk:15984562,sidewalk:11057330,floor_slab:12765893,exterior_wall:8640177,facade_window:5152706,curtain_wall_glass:7052974,storefront_window:2978705,facade_frame:14734783,facade_fin:3820629,facade_ground_band:11628357,facade_spandrel_band:9204317,facade_zone_band:7957084,mechanical_louver:3424324,window_backing:2502713,entrance_portal:13666885,balcony_slab:10450517,balcony_rail:3754060,interior_wall:15788247,door:15837023,stair_tread:12626162,elevator_shaft:8885917,elevator_cabin:15252841,elevator_landing_door:7320529,roof:6003337,roof_monitor:7451809,roof_parapet:8557709,roof_equipment:6254195,roof_auxiliary:5858666,landmark_crown:13666885,landmark_spire:13666885,entrance_canopy:15782780,grass:6662491,plaza:14076074,landscape_path:12032624,tree_trunk:7753779,tree_canopy:4165451,bench:7756872,street_light:5727594,street_tree_trunk:7753779,street_tree_canopy:4165451,street_bin:3754060,vehicle_body:5072240,vehicle_glass:2704206,pedestrian_body:9596020,pedestrian_head:14068101,street_asset:8623245,street_tree_asset:5215329,park_tree_asset:4162129,landscape_shrub_asset:4158266,street_light_asset:5858411,vehicle_asset:5537695,pedestrian_asset:12158318,plaza_feature:6666704,mechanical_roof:7373706,furniture_table:14064221,furniture_seating:6461650,furniture_storage:11826760,furniture_bed:11833033,furniture_fixture:14280162,furniture_equipment:7701899},d={data:null,streaming:null,geometryRevision:0,mode:"full",districtId:"all",buildingId:"",floorId:"",roomId:"",floorCameraPreset:"perspective",roomCameraPreset:"eye",roomLighting:"soft",heroRoomOnly:!0,heroRoomIds:new Set,enabledSemantics:new Set,daylight:!0,skyPreset:"clear",skyRotation:0,appearanceMode:"presentation",renderProfile:"interactive",geometryRenderSignature:"",geometryRebuildCount:0,standardGeometryContentSignature:"",navigationGeometryContentSignature:"",standardVisiblePrimitives:[],standardRenderStatusText:"",autoCutaway:!0,showOutlines:!1,showLabels:!1,showRoadMarkings:!1,highFidelityOverview:!1,highFidelityPreviousProfile:null,highFidelityOverviewAssetIds:new Set,prototypeCaptureAssetIds:new Set,xray:!1,hierarchyDisplay:null,captureExposure:null,presentationFocusId:null,showNavigation:!1,showValidation:!0,selectedPrimitive:null,doorStates:new Map,visiblePrimitives:[],assetObjectCache:new Map,contextLost:!1,contextLosses:0,presentationPreparing:!1,assetRenderGeneration:0,assetLoadState:{generation:0,expected:0,pending:0,loaded:0,fallback:0,failed:0,cached:0,ready:!0},assetReadyPromise:Promise.resolve(),materialTextureUrls:new Set,navigationKeys:new Set,keyboardNavigationActive:!1,cameraInteracting:!1,cameraDirty:!1,lastNavigationRenderTime:0,observationTargetIds:new Set,observationKind:""};let zi=null,mi=!1,ka=null,Ol=new Map,Ta=new Map,Bl=new Set,rs={};const H=Object.fromEntries(["scene-title","folder-input","reload-button","screenshot-button","hq-screenshot-button","export-render-view-button","mode-buttons","mode-hint","appearance-select","quality-select","sky-select","sky-rotation","sky-status","daylight-toggle","cutaway-toggle","outline-toggle","labels-toggle","markings-toggle","high-fidelity-toggle","district-select","building-select","floor-select","room-select","hero-room-toggle","focus-button","floor-plan-button","room-view-button","floor-camera-presets","floor-camera-buttons","room-camera-presets","room-camera-buttons","room-lighting","xray-toggle","hierarchy-display-button","paper-view-select","navigation-toggle","validation-toggle","grid-toggle","semantic-filters","viewport","scene-canvas","loading","toast","legend","render-status","metric-buildings","metric-floors","metric-rooms","metric-primitives","empty-inspector","inspector","entity-type","entity-id","entity-properties","door-button","route-button","validation-summary","validation-list","camera-iso","camera-high-fidelity","camera-top","camera-street","camera-reset"].map(i=>[i,document.getElementById(i)])),Me=new dx({canvas:H["scene-canvas"],antialias:!0,preserveDrawingBuffer:!0});Me.setPixelRatio(Math.min(window.devicePixelRatio,1.5));Me.outputColorSpace=Et;Me.shadowMap.enabled=!0;Me.shadowMap.type=Tu;Me.toneMapping=Au;Me.toneMappingExposure=1.12;const Ae=new qu;Ae.background=new Ee(12176849);Ae.fog=new ic(12176849,45e-5);const q=new Xt(46,1,.1,1e4);q.up.set(0,0,1);const we=new hx(q,Me.domElement);we.enableDamping=!0;we.dampingFactor=.075;we.screenSpacePanning=!1;we.zoomToCursor=!0;we.maxPolarAngle=Math.PI*.495;we.addEventListener("change",()=>{d.cameraDirty=!0,(d.streaming||fn(d.renderProfile))&&(clearTimeout(d.streamCameraTimer),d.streamCameraTimer=setTimeout(()=>Mc(),250))});we.addEventListener("end",()=>Mc());const cr=new cm(16056319,7438972,2.5),ss=new pm(16777215,.92);Ae.add(cr,ss);const et=new sh(16774102,2.8);et.position.set(-250,-180,420);et.castShadow=!0;et.shadow.mapSize.set(2048,2048);et.shadow.camera.left=-700;et.shadow.camera.right=700;et.shadow.camera.top=700;et.shadow.camera.bottom=-700;et.shadow.camera.near=1;et.shadow.camera.far=1400;et.shadow.bias=-12e-5;Ae.add(et,et.target);const Li=new At,Qn=new At,Mn=new At,_c=new At,Ir=new At,Ui=new At,Ts=new At,As=new At,Rs=new At,Lr=new At,Yn=new At,Cs=new At;Ae.add(Cs);Ae.add(Li,Qn,Mn,Ts,As,_c,Ir,Ui,Rs,Lr,Yn);const Zt=new yi(1,1,1);Zt.setAttribute("uv1",Zt.getAttribute("uv"));Zt.setAttribute("uv2",Zt.getAttribute("uv"));const Jv=new ph,kr=new Hv(async i=>{const[e,t]=JSON.parse(i),n=(await Jv.loadAsync(e)).scene;return Xv(n,t,async(r,s,a)=>{const o=document.createElement("canvas");return o.width=s,o.height=a,o.getContext("2d").drawImage(r,0,0,s,a),o})}),Qv=new ih,eM=new sv;let vs=new Ba(Me);vs.compileEquirectangularShader();const bh=new Map,tM=new Map,yc=new Set,xc=new Map,Aa=new Map;let vr=null,ds=null,as="";const Mr=new Map,os=new Map,zl=bv();Ae.add(zl);const nn=new ni(new eh(Zt),new Fn({color:16056197,linewidth:2,depthTest:!1}));nn.renderOrder=20;nn.visible=!1;_c.add(nn);const Dr=rM(1e3,50);Ae.add(Dr);Ps();const yu=new Tm,Xo=new xe;let hr=null,xu=null;const nM={overview:"Overview: roads and building shells only.",building:"Building: selected interior shown with an automatic shell cutaway.",floor:"Floor: selected level isolated; its roof is hidden automatically.",floor_plan:"Floor plan: only the selected floor is visible from a top-down view.",room:"Room: only the selected room, its boundary, door, and furnishings are visible.",full:"Full scene: all compiled geometry is visible."},Sh=new Set(["roads","district","root"]);function wh(i){if(!d.highFidelityOverview||d.mode!=="overview"||!i.metadata?.resolved_asset||!i.metadata?.asset_id)return!1;const e=d.data?.layerMap.get(i.layer_id)?.layer_type||"unknown";return Sh.has(e)&&d.highFidelityOverviewAssetIds.has(i.id)}function iM(i){const e=new Map([["tree",6],["shrub",4],["street_light_asset",5],["street_furniture",5],["vehicle_asset",3],["pedestrian_asset",2],["flower_cluster",4],["playground_equipment",1]]),t=i.filter(s=>{if(!s.metadata?.resolved_asset||!s.metadata?.asset_id)return!1;const a=d.data?.layerMap.get(s.layer_id)?.layer_type||"unknown";if(!Sh.has(a))return!1;const o=s.semantic_class;return["street_tree_asset","park_tree_asset","parcel_tree_asset","parcel_shrub_asset","landscape_shrub_asset","street_light_asset","bench","street_bench","street_planter","vehicle_asset","pedestrian_asset","person_asset","flower_cluster","playground_equipment"].includes(o)}),n=s=>{const a=s.semantic_class;return["street_tree_asset","park_tree_asset","parcel_tree_asset"].includes(a)?"tree":["parcel_shrub_asset","landscape_shrub_asset"].includes(a)?"shrub":["bench","street_bench","street_planter"].includes(a)?"street_furniture":a},r=new Set;for(const[s,a]of e){const o=t.filter(h=>n(h)===s).sort((h,u)=>String(h.id).localeCompare(String(u.id))),l=[],c=new Set;for(const h of o){const u=h.metadata.asset_id;if(!c.has(u)&&(c.add(u),l.push(h),l.length>=a))break}if(l.length<a){for(const h of o)if(l.includes(h)||l.push(h),l.length>=a)break}l.forEach(h=>r.add(h.id))}return r}const Eh={perspective:"Floor 3D",top:"Floor top",corridor:"Corridor",core:"Stair / lift"};function rM(i,e){const t=[],n=i/2;for(let s=-n;s<=n;s+=e)t.push(-n,s,-.19,n,s,-.19),t.push(s,-n,-.19,s,n,-.19);const r=new yt;return r.setAttribute("position",new mt(t,3)),new ni(r,new Fn({color:2703675,transparent:!0,opacity:.34}))}function Ps(){const i=Ae.userData.renderingHints||{},e=Number.isFinite(i.fog_density_scale)?i.fog_density_scale:1,t=Number.isFinite(i.exposure_scale)?i.exposure_scale:1,n=Number.isFinite(i.sun_intensity_scale)?i.sun_intensity_scale:1,r=d.daylight?12176849:1055771;Ae.background=new Ee(r),Ae.backgroundRotation.set(0,0,0),Ae.environmentRotation.set(0,0,0),Ae.backgroundIntensity=1,Ae.environmentIntensity=1,zl.visible=!1,Ae.fog.color.setHex(r);const s=d.data?.city?.bounds,a=s?Math.hypot(s.max_x-s.min_x,s.max_y-s.min_y):800;Ae.fog.density=(d.daylight?45e-5:9e-4)*e*Math.min(1,800/Math.max(800,a)),Me.toneMappingExposure=d.captureExposure??(d.daylight?1.12:1.3)*t,cr.color.setHex(d.daylight?16056319:15269880),cr.groundColor.setHex(d.daylight?7438972:3162172),cr.intensity=d.daylight?2.5:3,ss.color.setHex(d.daylight?16777215:14216936),ss.intensity=d.daylight?.92:.72,et.intensity=(d.daylight?2.8:3.4)*n,et.color.setHex(16774102);const o=Ms(d.data?.raw.config),l=Mr.get(o.url);if(o.preset&&l&&Bt[d.renderProfile].environment){const c=o.preset,h=Av(l.analysis,Number.isFinite(i.sun_azimuth_deg)?i.sun_azimuth_deg:215,d.skyRotation);Ae.background=l.source,Ae.backgroundRotation.copy(h.rotation),Ae.environmentRotation.copy(h.rotation),Ae.backgroundBlurriness=0,Ae.backgroundIntensity=c.background_intensity??.5,Ae.environmentIntensity=c.environment_intensity??.65,Ae.fog.color.setRGB(...l.analysis.horizon).multiplyScalar(Ae.backgroundIntensity),Me.toneMappingExposure=d.captureExposure??(c.exposure??1)*t,_u(et,h.sun),et.color.set(c.sun_color||"#fff3d6"),et.intensity=(c.sun_intensity??2.8)*n,cr.intensity=.7,ss.intensity=.25;const u=d.data?.geometry.primitives.find(f=>f.metadata?.ground_plane);if(u&&["overview","building","full"].includes(d.mode)&&d.districtId==="all"){const f=d.data.geometry.materials.find(p=>p.id===u.material_id);Sv(zl,u,f,a,l.analysis.horizon,Ae.backgroundIntensity)}}else{const c=(Number.isFinite(i.sun_azimuth_deg)?i.sun_azimuth_deg:215)*Math.PI/180,h=(Number.isFinite(i.sun_elevation_deg)?i.sun_elevation_deg:54)*Math.PI/180;_u(et,new P(Math.cos(c)*Math.cos(h),Math.sin(c)*Math.cos(h),Math.sin(h)))}d.mode==="room"&&d.roomLighting==="soft"&&(cr.intensity=2.8,ss.intensity=1.35,et.intensity=1.8,Me.toneMappingExposure=1.08,Ae.fog.density=0),Dr.material.color.setHex(d.daylight?7310729:2703675),Dr.material.opacity=d.daylight?.3:.34,H["sky-status"]&&(H["sky-status"].textContent=o.preset?l?`${o.preset.label} · HDR sky + lighting`:"Loading sky…":["floor","floor_plan","room"].includes(d.mode)?"Plain background for indoor inspection":!d.data?.raw.config?.sky_presets?.[d.skyPreset]&&d.skyPreset!=="none"?"Sky pack not installed in this export":"Sky disabled in this view / quality mode")}function sM(i){if(!i||typeof i!="object")return;Ae.userData.renderingHints=i;const e=Number(i.sun_azimuth_deg),t=Number(i.sun_elevation_deg);if(Number.isFinite(e)&&Number.isFinite(t)){const n=e*Math.PI/180,r=Math.max(8,Math.min(82,t))*Math.PI/180,s=520;et.position.set(Math.cos(n)*Math.cos(r)*s,Math.sin(n)*Math.cos(r)*s,Math.sin(r)*s).add(et.target.position)}Ps()}function aM(){const i=window.__CITYG_RENDER_PROFILE__,e=new URLSearchParams(window.location.search).get("quality"),t=window.localStorage?.getItem("cityg.renderProfile");return[i,e,t,"interactive"].find(n=>Bt[n])}function Nn(i,{persist:e=!1}={}){const t=Bt[i]?i:"interactive",n=Bt[t];d.renderProfile==="navigation"&&["presentation","interactive"].includes(t)&&Mn.children.length&&(d.presentationPreparing=!0),["presentation","interactive"].includes(t)||(d.presentationPreparing=!1),t==="navigation"&&d.renderProfile!=="navigation"&&Bh(),d.renderProfile=t,Me.setDrawingBufferSize(H.viewport.clientWidth,H.viewport.clientHeight,xh(H.viewport.clientWidth,H.viewport.clientHeight,n.pixelRatio())),Me.shadowMap.enabled=n.shadows,et.castShadow=n.shadows;const r=Math.min(Me.capabilities.maxTextureSize,t==="snapshot"?4096:t==="presentation"?2048:1024);return et.shadow.mapSize.x!==r&&(et.shadow.mapSize.set(r,r),et.shadow.map?.dispose(),et.shadow.map=null),we.enableDamping=!["review","navigation","paper_capture","snapshot"].includes(t),n.environment?vr&&(Ae.environment=vr.texture):Ae.environment=null,n.environment&&d.data&&Ec(d.data.raw.config),H["quality-select"]&&(H["quality-select"].value=t),e&&window.localStorage?.setItem("cityg.renderProfile",t),vc(),n}function vc(){if(mi)return;const{clientWidth:i,clientHeight:e}=H.viewport;Me.setDrawingBufferSize(i,e,xh(i,e,Bt[d.renderProfile].pixelRatio())),q.aspect=i/Math.max(1,e),q.updateProjectionMatrix(),d.cameraDirty=!0,d.data&&fn(d.renderProfile)&&(clearTimeout(d.streamCameraTimer),d.streamCameraTimer=setTimeout(()=>Mc(),250))}new ResizeObserver(vc).observe(H.viewport);function oM(i){if(!d.navigationKeys.size)return;const e=d.navigationKeys.has("shift")?3:1,t=q.position.clone().sub(we.target),n=Math.max(1,t.length()),r=Math.max(.55,n*.42)*i*e,s=q.up.clone().normalize(),a=we.target.clone().sub(q.position);a.z=0,a.lengthSq()<1e-8&&a.set(0,1,0),a.normalize();const o=a.clone().cross(s).normalize(),l=new P;d.navigationKeys.has("w")&&l.addScaledVector(a,r),d.navigationKeys.has("s")&&l.addScaledVector(a,-r),d.navigationKeys.has("a")&&l.addScaledVector(o,-r),d.navigationKeys.has("d")&&l.addScaledVector(o,r),d.navigationKeys.has("q")&&l.addScaledVector(s,-r),d.navigationKeys.has("e")&&l.addScaledVector(s,r),q.position.add(l),we.target.add(l);const c=(d.navigationKeys.has("arrowleft")?1:0)-(d.navigationKeys.has("arrowright")?1:0),h=(d.navigationKeys.has("arrowup")?1:0)-(d.navigationKeys.has("arrowdown")?1:0);if(c||h){const u=q.position.clone().sub(we.target),f=.95*i*e;if(u.applyAxisAngle(s,c*f),h){const p=s.clone().cross(u).normalize(),_=u.clone().applyAxisAngle(p,h*f),y=_.angleTo(s);y>.1&&y<Math.PI*.49&&u.copy(_)}q.position.copy(we.target).add(u)}}function Th(){if(!d.data||d.renderProfile==="prototype_capture")return;d.data.depthPrimitives!==d.data.geometry.primitives&&(d.data.sceneTop=d.data.geometry.primitives.reduce((e,t)=>Math.max(e,t.center.z+t.size.z/2),0),d.data.depthPrimitives=d.data.geometry.primitives);const i=Ov(q.position,we.target,d.data.sceneTop,d.mode);i!==null&&Math.abs(q.near-i)>1e-5&&(q.near=i,q.updateProjectionMatrix(),d.cameraDirty=!0)}let vu=performance.now();function Ah(){if(requestAnimationFrame(Ah),mi||d.contextLost||["prototype_capture","paper_capture"].includes(d.renderProfile))return;const i=performance.now(),e=Math.min(.05,(i-vu)/1e3);vu=i,oM(e);const t=we.update();if(Th(),d.presentationPreparing&&!Dh()){const n=gi();H["render-status"].textContent=`Preparing ${d.renderProfile} · ${n.loaded} models ready · ${n.pending} pending · Navigation preview retained`,(d.cameraDirty||t)&&(Me.render(Ae,q),d.cameraDirty=!1);return}if(d.streaming&&!["review","navigation","prototype_capture"].includes(d.renderProfile)){const n=d.cameraInteracting||t||d.navigationKeys.size>0,r=d.assetLoadState.pending>0||d.streaming.status.pending>0||[...d.materialTextureUrls].some(s=>xc.get(s)==="pending");(n||d.cameraDirty&&!r)&&(Me.render(Ae,q),d.cameraDirty=!1)}else if(!["review","navigation","prototype_capture"].includes(d.renderProfile))(d.cameraDirty||t||d.navigationKeys.size>0)&&(Me.render(Ae,q),d.cameraDirty=!1);else if(d.renderProfile==="navigation"){const n=d.cameraInteracting||d.cameraDirty||t||d.navigationKeys.size>0,r=d.cameraInteracting?55:0;n&&i-d.lastNavigationRenderTime>=r&&(Me.render(Ae,q),d.lastNavigationRenderTime=i,d.cameraDirty=!1)}else(d.cameraDirty||t||d.navigationKeys.size>0)&&(Me.render(Ae,q),d.cameraDirty=!1)}Ah();async function Rh(){d.data&&zi?.reset(),Zn(!0,"Loading CityG manifests");let i=await fetch("/api/config",{cache:"no-store"});if(i.ok||(i=await fetch("./viewer-config.json",{cache:"no-store"})),!i.ok)throw new Error("Viewer configuration is unavailable");const e=await i.json(),t=e.source==="portable_export"?"./scene/":"/scene/",n=async(o,l=!1,c)=>{const h=await fetch(`${t}${o}`,{cache:"no-store",signal:c});if(!h.ok){if(l)throw new Error(`Missing required scene file: ${o}`);return null}return h.json()},r=await Promise.all([...za.map(o=>n(o,!0)),...Fl.map(o=>n(o,!1))]),s=[...za,...Fl],a=Object.fromEntries(s.map((o,l)=>[o,r[l]]));a.config=e,await Ch(a,n),Lh(a),Ph(a,n)}async function lM(i){d.data&&zi?.reset();const e=[...i],t=e.filter(o=>o.name==="geometry_manifest.json");if(!t.length)throw new Error("Selected folder has no geometry_manifest.json");t.sort((o,l)=>o.webkitRelativePath.length-l.webkitRelativePath.length);const n=t[0].webkitRelativePath.slice(0,-22),r=new Map;for(const o of e)o.webkitRelativePath.startsWith(n)&&(o.webkitRelativePath.slice(n.length).includes("/")||r.set(o.name,o));for(const o of za)if(!r.has(o))throw new Error(`Selected scene is missing ${o}`);Zn(!0,"Reading local scene folder");const s={};for(const o of[...za,...Fl])s[o]=r.has(o)?JSON.parse(await r.get(o).text()):null;s.config={label:n.replace(/\/$/,"")||"Local folder",source:"browser"};const a=async o=>{if(!r.has(o))throw new Error(`Missing geometry chunk: ${o}`);return JSON.parse(await r.get(o).text())};await Ch(s,a),Lh(s),Ph(s,a)}async function Ch(i,e){const t=i["geometry_manifest.json"];if(t.streaming){if(t.streaming.version!==1)throw new Error("Unsupported CityG geometry streaming version");t.primitives=[];for(const n of t.streaming.overview){const r=await e(n.file,!0);if(!Array.isArray(r?.primitives)||r.primitives.length!==n.count)throw new Error(`Invalid overview chunk: ${n.file}`);t.primitives=t.primitives.concat(r.primitives)}}}function Ph(i,e){const t=i["geometry_manifest.json"];t.streaming&&(d.streaming=new ov(t.streaming,t.primitives,e,n=>{if(d.data.geometry.primitives=n,d.geometryRevision+=1,cM(),d.mode==="room"){const s=[...d.observationTargetIds].map(a=>d.data.hierarchy.entities.get(a)).find(a=>a?.type==="room");s&&(d.roomId=s.entity.id,d.floorId=s.floorId,d.buildingId=s.buildingId)}const r=new Set(n.map(s=>s.id));for(const[s,a]of d.assetObjectCache)r.has(a.userData.entry?.id)||(a.removeFromParent(),a.traverse(o=>o.userData.citygOwnedMaterials?.forEach(l=>l.dispose())),d.assetObjectCache.delete(s));Ls(),$e()},n=>{n.failed&&Pt(`Geometry loading failed: ${n.error}`),Ra()}),Ya(),ii())}function cM(){const i=new Map;for(const e of d.data.geometry.primitives){if(e.semantic_class!=="interior_wall")continue;const t=e.metadata?.room_ids||(d.data.hierarchy.entities.get(e.owner_id)?.type==="room"?[e.owner_id]:[]);for(const n of t)i.has(n)||i.set(n,[]),i.get(n).push(e)}d.data.roomWalls=i,d.data.roomWallIds=new Set(i.keys())}function Ih(){return qv(q,ka||H.viewport.clientHeight*Me.getPixelRatio(),et.position.clone().sub(et.target.position).toArray())}function Mc(){mi||!d.data||(fn(d.renderProfile)?$e():Ya())}function Ya(){if(!d.streaming||!d.data)return Promise.resolve();const i=new Set(d.observationTargetIds);for(const n of i){const r=d.data.hierarchy.entities.get(n)?.buildingId;r&&i.add(r)}const e=fn(d.renderProfile)?Ih():null,t=lv(d.data.geometry.streaming,{profile:d.renderProfile,mode:d.mode,buildingId:d.buildingId,kind:d.observationKind,targets:[...i],camera:q.position,focus:we.target,screenMeasure:e?n=>e.measure(jv(n)):null});return d.streaming.request(t)}function Ra(){if(!d.streaming)return;const i=d.data.geometry,e=d.streaming.status;H["render-status"].textContent=`${d.visiblePrimitives.length.toLocaleString()} visible · ${i.primitives.length.toLocaleString()} resident / ${i.streaming.total_primitives.toLocaleString()} total · ${e.failed?"geometry error":e.pending?`loading ${e.pending} chunks`:e.loaded_chunks?"local detail + city LOD":"city LOD"} · ${d.renderProfile}`}function Lh(i){d.streaming?.dispose(),d.streaming=null,d.geometryRevision=0;const e=i["geometry_manifest.json"],t=i["city.json"],n=i["navigation.json"]||e.navigation||{nodes:[],edges:[]},r=i["interactions.json"]||{state_machines:e.state_machines||[]},s=i["activation_manifest.json"]||{layers:e.layers||[],activation_tiers:e.activation_tiers||[],building_prototypes:{}},a=dM(t),o=new Map(s.layers.map(m=>[m.id,m])),c=[i["validation_report.json"],i["geometry_validation_report.json"],i["interaction_smoke_report.json"],i["usd_validation_report.json"]].filter(Boolean).flatMap(m=>m.issues||[]),h=new Set(c.flatMap(m=>[m.entity_id,...m.violating_entities||[]]).filter(Boolean)),u=new Map;for(const m of e.primitives){if(m.semantic_class!=="interior_wall")continue;const E=Array.isArray(m.metadata?.room_ids)?m.metadata.room_ids:[],w=a.entities.get(m.owner_id)?.type==="room",x=E.length?E:w?[m.owner_id]:[];for(const T of x)u.has(T)||u.set(T,[]),u.get(T).push(m)}const f=new Set(u.keys()),p=new Set([...a.entities.values()].filter(m=>m.type==="room"&&m.entity.metadata?.detail_tier==="hero").map(m=>m.entity.id));d.data={raw:i,geometry:e,city:t,navigation:n,interactions:r,activation:s,hierarchy:a,layerMap:o,issues:c,errorIds:h,roomWallIds:f,roomWalls:u,heroRoomIds:p},zi?.available(i.config?.source==="portable_export"&&i.config?.files?.includes("task_replay.json")),sM(e.metadata?.rendering_profile||t.metadata?.rendering_profile),d.heroRoomIds=p,d.heroRoomOnly=p.size>0,d.highFidelityOverview=!1,d.highFidelityPreviousProfile=null,d.highFidelityOverviewAssetIds=new Set,H["hero-room-toggle"].checked=d.heroRoomOnly,H["high-fidelity-toggle"].checked=!1,H["camera-high-fidelity"].classList.remove("active"),H["hero-room-toggle"].disabled=p.size===0;const _=window.__CITYG_RENDER_PROFILE__||new URLSearchParams(window.location.search).get("quality");Nn(e.streaming&&!_?"navigation":aM()),d.mode=(e.streaming?.total_primitives||e.primitives.length)>=Zv?"overview":"full",Rc(),kr.clear(),d.assetRenderGeneration+=1,d.enabledSemantics=new Set(e.streaming?.semantics||e.primitives.map(m=>m.semantic_class)),d.doorStates=new Map(r.state_machines.map(m=>[m.id,m.initial_state])),d.selectedPrimitive=null,d.geometryRenderSignature="",d.geometryRebuildCount=0,d.standardGeometryContentSignature="",d.navigationGeometryContentSignature="",d.standardVisiblePrimitives=[],d.standardRenderStatusText="",Wt(Mn);const y=window.__CITYG_INITIAL_OBSERVATION_VIEW__||null,g=!!(Array.isArray(y?.camera_position)&&Array.isArray(y?.look_at));y&&Vh(y),Wh(),H["scene-title"].textContent=`${t.name} · ${i.config?.label||t.id}`,uM(),Ec(i.config),$e(),NM(),Nr(),g||Fi("iso"),Zn(!1),window.citygObservation.ready=!0,zM(i.config),Pt(`Loaded ${e.primitives.length.toLocaleString()} primitives`)}function dM(i){const e=new Map,t=(r,s,a,o={})=>e.set(r.id,{entity:r,type:s,parentId:a,...o});t(i,"city",null);for(const r of i.road_network?.junctions||[])t(r,"junction",i.id);for(const r of i.road_network?.segments||[])t(r,"road_segment",i.id);for(const r of i.rivers||[])t(r,"river",i.id);for(const r of i.bridges||[])t(r,"bridge",i.id);for(const r of i.districts||[]){t(r,"district",i.id,{districtId:r.id});for(const s of r.parcels||[]){t(s,"parcel",r.id,{districtId:r.id});for(const a of s.buildings||[]){t(a,"building",s.id,{districtId:r.id,buildingId:a.id});const o=new Map((a.floors||[]).map(l=>[Number(l.level),l]));for(const l of a.vertical_connectors||[]){const c=[...o.entries()].filter(([h])=>h>=Number(l.from_level)&&h<=Number(l.to_level)).map(([,h])=>h.id);t(l,"vertical_connector",a.id,{districtId:r.id,buildingId:a.id,floorIds:c})}for(const l of a.floors||[]){t(l,"floor",a.id,{districtId:r.id,buildingId:a.id,floorId:l.id});for(const c of l.rooms||[]){t(c,"room",l.id,{districtId:r.id,buildingId:a.id,floorId:l.id});for(const h of(l.objects||[]).filter(u=>u.room_id===c.id))t(h,"interior_object",c.id,{districtId:r.id,buildingId:a.id,floorId:l.id})}for(const c of l.doors||[])t(c,"door",l.id,{districtId:r.id,buildingId:a.id,floorId:l.id,roomIds:[c.room_a_id,c.room_b_id].filter(Boolean)})}}}}function n(r){const s=[];let a=e.get(r);for(;a;)s.push(a.entity.id),a=a.parentId?e.get(a.parentId):null;return s}return{entities:e,lineage:n}}function uM(){const{city:i,hierarchy:e,geometry:t}=d.data;Is(H["district-select"],[{value:"all",label:"All districts"},...i.districts.map(o=>({value:o.id,label:`${o.name} · ${o.function}`}))],d.districtId),i.districts.some(o=>o.id===d.districtId)||(d.districtId="all"),bc(),H["semantic-filters"].replaceChildren();const n=[...new Set(t.streaming?.semantics||t.primitives.map(o=>o.semantic_class))].sort();for(const o of n){const l=document.createElement("label"),c=document.createElement("input");c.type="checkbox",c.checked=!0,c.addEventListener("change",()=>{c.checked?d.enabledSemantics.add(o):d.enabledSemantics.delete(o),$e()});const h=document.createElement("span");h.className="swatch",h.style.background=`#${(Pr[o]||9085852).toString(16).padStart(6,"0")}`;const u=document.createElement("span");u.textContent=o.replaceAll("_"," "),l.append(c,h,u),H["semantic-filters"].append(l)}const r=[...e.entities.values()].filter(o=>o.type==="building"),s=[...e.entities.values()].filter(o=>o.type==="floor"),a=[...e.entities.values()].filter(o=>o.type==="room");H["metric-buildings"].textContent=r.length,H["metric-floors"].textContent=s.length,H["metric-rooms"].textContent=a.length,ii(),Yh()}function ii(){H["mode-hint"].textContent=d.renderProfile==="navigation"?"Navigation preview: lightweight building silhouettes and road context; switch to Presentation for final materials.":d.mode==="overview"&&d.highFidelityOverview?"High-fidelity overview: real outdoor GLB assets are loaded; interiors remain hidden.":nM[d.mode],d.streaming&&(H["mode-hint"].textContent+=" · Streamed scene: city LOD; select a building or approach the street in Presentation for local detail."),Ka()}function Ha(i,{focus:e=!0,render:t=!0}={}){const n=!!i;if(n===d.highFidelityOverview&&(!n||d.mode==="overview")){e&&n&&Fi("iso");return}if(n)d.highFidelityPreviousProfile=d.renderProfile,d.highFidelityOverview=!0,d.mode="overview",Nn("high_fidelity"),e&&Fi("iso"),Pt("High-fidelity overview enabled; loading outdoor assets…");else{d.highFidelityOverview=!1;const r=d.highFidelityPreviousProfile;d.highFidelityPreviousProfile=null,r&&Bt[r]&&Nn(r),Pt("High-fidelity overview disabled")}H["high-fidelity-toggle"]&&(H["high-fidelity-toggle"].checked=n),H["camera-high-fidelity"]&&H["camera-high-fidelity"].classList.toggle("active",n),H["mode-buttons"].querySelectorAll("button").forEach(r=>{r.classList.toggle("active",r.dataset.mode===d.mode)}),ii(),t&&$e()}function Ka(){if(H["room-camera-presets"]&&(H["room-camera-presets"].hidden=d.mode!=="room"||!d.roomId,H["room-camera-buttons"].querySelectorAll("button[data-room-camera]").forEach(e=>{e.classList.toggle("active",e.dataset.roomCamera===d.roomCameraPreset)})),!H["floor-camera-presets"])return;const i=!!(d.buildingId&&d.floorId);H["floor-camera-presets"].hidden=!i,H["floor-camera-buttons"]?.querySelectorAll("button[data-floor-camera]").forEach(e=>{e.classList.toggle("active",e.dataset.floorCamera===d.floorCameraPreset)})}function Is(i,e,t){i.replaceChildren(...e.map(({value:n,label:r})=>{const s=document.createElement("option");return s.value=n,s.textContent=r,s.selected=n===t,s})),e.length&&!e.some(n=>n.value===t)&&(i.value=e[0].value)}function bc(){const i=[...d.data.hierarchy.entities.values()].filter(e=>e.type==="building"&&(d.districtId==="all"||e.districtId===d.districtId));i.some(e=>e.entity.id===d.buildingId)||(d.buildingId=i[0]?.entity.id||""),Is(H["building-select"],i.map(e=>({value:e.entity.id,label:`${e.entity.name} · ${e.entity.function}`})),d.buildingId),$a()}function $a(){const i=[...d.data.hierarchy.entities.values()].filter(e=>e.type==="floor"&&e.buildingId===d.buildingId).sort((e,t)=>e.entity.level-t.entity.level);i.some(e=>e.entity.id===d.floorId)||(d.floorId=i[0]?.entity.id||""),Is(H["floor-select"],i.map(e=>({value:e.entity.id,label:`Level ${e.entity.level} · ${e.entity.id}`})),d.floorId),Ls()}function Ls(){const i=d.heroRoomOnly&&d.heroRoomIds.size>0,e=[...d.data.hierarchy.entities.values()].filter(t=>t.type==="room"&&t.floorId===d.floorId&&(!i||d.heroRoomIds.has(t.entity.id))&&Za(t.entity.id)).sort((t,n)=>t.entity.function==="corridor"&&n.entity.function!=="corridor"?-1:t.entity.function!=="corridor"&&n.entity.function==="corridor"?1:t.entity.id.localeCompare(n.entity.id));e.some(t=>t.entity.id===d.roomId)||(d.roomId=e.find(t=>t.entity.function!=="corridor")?.entity.id||e[0]?.entity.id||""),Is(H["room-select"],e.map(t=>({value:t.entity.id,label:`${t.entity.name||t.entity.id} · ${t.entity.function}`})),d.roomId)}function Za(i){if(!d.data?.roomWallIds?.has(i))return!1;const t=d.data.hierarchy.entities.get(i)?.entity;if(!t)return!1;const n=d.data.roomWalls.get(i)||[];return n.length?uv(t,n):!1}function $e(){if(!d.data||d.contextLost)return;if(Th(),Ps(),Ec(d.data.raw.config),d.cameraDirty=!0,Ya(),Dr.visible=!["floor_plan","room"].includes(d.mode)&&H["grid-toggle"].checked,d.renderProfile==="navigation"){hM(),Ra();return}Mn.visible=d.presentationPreparing,Sc(!d.presentationPreparing);const i=Xh();if(d.standardGeometryContentSignature===i&&Li.children.length>0){d.visiblePrimitives=d.standardVisiblePrimitives,d.geometryRenderSignature=Ur(),H["metric-primitives"].textContent=d.visiblePrimitives.length.toLocaleString(),H["render-status"].textContent=d.standardRenderStatusText,Ga(),Ra();return}d.materialTextureUrls=new Set,Wt(Li),Rc(),Wt(Ir),Wt(Ui),Wt(Ts),Wt(As),Wt(Rs),Wt(Lr),Wt(Yn),Wt(Cs),d.highFidelityOverviewAssetIds=d.highFidelityOverview&&d.mode==="overview"?iM(d.data.geometry.primitives):new Set,d.prototypeCaptureAssetIds=null,d.prototypeCaptureAssetIds=d.renderProfile==="prototype_capture"?$v(d.data.geometry.primitives.filter(kl),q.position,d.observationKind):new Set;const e=new Map,t=Uh(),n=new Map,r=new Map(d.data.geometry.materials.map(o=>[o.id,o]));let s=d.data.geometry.primitives.filter(kl);if(Ol=new Map,Ta=new Map,Bl=new Set,rs={candidates:s.length,culled:0,reduced_assets:0,original_assets:0,shadow_only:0},fn(d.renderProfile)){const o=Ih(),l=d.data.raw.config?.asset_lods||{};s=s.filter(c=>{const h=o.measure(gu(c));if(!h.visible&&!h.shadow||h.pixels<.75)return rs.culled++,!1;if(h.visible||rs.shadow_only++,["facade_window","storefront_window","curtain_wall_glass"].includes(c.semantic_class)&&n.set(c.id,h.visible&&h.pixels>=64),ya(c)){const u=c.metadata.asset_id,f=Yv(u,h.pixels,l);Ol.set(c.id,f),Ta.set(f,Math.max(Ta.get(f)||0,h.pixels)),h.pixels>=8&&Bl.add(c.id),rs[f===u?"original_assets":"reduced_assets"]++}return!0})}if(fn(d.renderProfile)){const o=new kt;for(const l of s)(ya(l)||["exterior_wall","interior_wall","roof","roof_parapet","floor_slab","balcony_slab","tree_canopy","street_tree_canopy","vehicle_body","pedestrian_body"].includes(l.semantic_class))&&o.union(gu(l));Kv(et,o)}const a=s.filter(ya);d.data.groundEdgePrimitives!==d.data.geometry.primitives&&(d.data.groundEdges=Rv(d.data.geometry.primitives,d.data.hierarchy.entities),d.data.groundEdgePrimitives=d.data.geometry.primitives),d.visiblePrimitives=s,d.geometryRenderSignature=Ur(),d.geometryRebuildCount+=1;for(const o of s){if(ya(o))continue;const l=d.data.layerMap.get(o.layer_id)?.layer_type||"unknown",c=d.data.hierarchy.entities.get(o.owner_id),h=l==="building_shell"&&c?.buildingId===d.buildingId&&["building","floor"].includes(d.mode),u=yh(d.hierarchyDisplay,c,l),f=u||l==="building_shell"&&(d.xray||d.autoCutaway&&h),p=d.showValidation&&PM(o),_=r.get(o.material_id),y=fM(o,_),g=o.semantic_class==="parcel_ground"?o.metadata?.parcel_id||o.owner_id:"",m=!fn(d.renderProfile)||n.get(o.id)===!0,E=`${o.primitive_type}|${o.material_id}|${o.semantic_class}|${u?"scoped":f?"xray":"solid"}|${p?"error":"normal"}|${y||"default_uv"}|${o.primitive_type==="path_mesh"?o.id:""}|${vh(o,t)}|${g}|glass:${m}`;e.has(E)||e.set(E,{entries:[],material:_,primitiveType:o.primitive_type,semantic:o.semantic_class,xray:f,scopedShell:u,error:p,facade:!1,uvBucket:y,detailedGlass:m}),e.get(E).entries.push(o),e.get(E).facade||=String(o.metadata?.facade_system||"").startsWith("grammar_")}for(const o of e.values()){const l=o.material||{},c=l.display_color?new Ee(...l.display_color):new Ee(9085852),h=d.appearanceMode==="semantic",u=d.appearanceMode==="clay",f=h||o.error,p=["facade_window","storefront_window","curtain_wall_glass"].includes(o.semantic),_=p?new Ee(7902624):new Ee(o.facade?14012354:12370621),y={color:f?16777215:u?_:c,roughness:u?p?.28:.82:l.roughness??.75,metalness:u?0:l.metallic??0,transparent:o.xray||(l.opacity??1)<1||p&&!u&&!h,opacity:o.xray?o.scopedShell?d.hierarchyDisplay.shell_opacity:.16:p&&!u&&!h?.88:l.opacity??1,depthWrite:!o.xray,clippingPlanes:o.scopedShell?Fh():[],vertexColors:f,polygonOffset:!1},g=Bt[d.renderProfile].physicalGlass&&o.detailedGlass&&p&&!u&&!h&&!o.xray,m=d.data.raw.config.river_surface||{},E=o.semantic==="river_water"&&!o.error&&!o.xray&&!u&&!h&&Bt[d.renderProfile].materialTextures&&m.enabled!==!1?(d.data.city.rivers||[]).find(T=>T.id===(o.entries[0].metadata?.river_id||o.entries[0].owner_id)):null,w=g?new mn({...y,transmission:o.semantic==="curtain_wall_glass"?.42:.28,thickness:.08,ior:1.46,clearcoat:.16,clearcoatRoughness:.22,envMapIntensity:1.35}):E?new mn({...y,metalness:0,roughness:.34,ior:1.333,clearcoat:0,envMapIntensity:.65,transparent:!1,opacity:1}):new Dn(y);if(E&&Fv(w,E,m),o.error?(w.emissive.setHex(7016464),w.emissiveIntensity=.65):h&&!o.xray?(w.emissive.setHex(Pr[o.semantic]||9085852),w.emissiveIntensity=d.daylight?.13:.2):!u&&p&&!o.xray&&(w.emissive.copy(c).multiplyScalar(.1),w.emissiveIntensity=d.daylight?.32:.45),(Bt[d.renderProfile].materialTextures||d.renderProfile==="review"&&d.observationKind==="building_exterior"&&o.entries.some(T=>d.observationTargetIds.has(d.data.hierarchy.entities.get(T.owner_id)?.buildingId)))&&!h&&!u&&!o.xray){Mu(w,o.material?.id);const T=d.data.raw.config.ground_surface||{};if(o.semantic==="parcel_ground"&&!o.error&&T.enabled!==!1){const L=o.entries[0],C=d.data.hierarchy.entities.get(L.metadata?.parcel_id||L.owner_id)?.entity,R=Cv(C,l.id,d.data.groundEdges);if(R){const v=R.green?"courtyard_paving":"parcel_lawn";d.data.raw.config.material_textures?.[l.id]?.base_color&&w.color.setHex(16777215);const b=Iv(w,R,{strength:T.strength??1,otherScale:r.get(v)?.texture_scale_m||4});Mu(w,v,r.get(v),b)}}}const x=new bs(Nh(o.primitiveType,o.uvBucket,o.entries[0],l),w,o.entries.length);x.userData.entries=o.entries,x.castShadow=["exterior_wall","roof","roof_parapet","balcony_slab","tree_canopy","street_tree_canopy","vehicle_body","pedestrian_body","bridge_deck","bridge_parapet","bridge_abutment","river_bank"].includes(o.semantic),x.receiveShadow=!0,o.entries.forEach((T,L)=>{if(x.setMatrixAt(L,Ns(T)),f){const C=o.error?new Ee(16728642):h?new Ee(Pr[T.semantic_class]||9085852):c;x.setColorAt(L,C)}}),x.instanceMatrix.needsUpdate=!0,x.instanceColor&&(x.instanceColor.needsUpdate=!0),x.computeBoundingSphere(),Li.add(x)}H["metric-primitives"].textContent=s.length.toLocaleString(),H["render-status"].textContent=`${s.length.toLocaleString()} / ${d.data.geometry.primitives.length.toLocaleString()} primitives · ${e.size} groups · ${a.length} GLB · ${d.renderProfile}`,d.standardGeometryContentSignature=i,d.standardVisiblePrimitives=s,d.standardRenderStatusText=H["render-status"].textContent,MM(a),d.mode!=="floor_plan"&&(d.showRoadMarkings&&AM(),d.showOutlines&&RM(),d.showLabels&&CM(),d.showNavigation&&IM()),d.mode==="room"&&wM(),["floor","floor_plan"].includes(d.mode)&&TM(),bM(),Ga(),Ra()}function Sc(i){for(const e of[Li,Qn,Ts,As,_c,Ir,Ui,Rs,Lr,Yn,Cs])e.visible=i}function Dh(){if(!d.presentationPreparing)return!0;const i=gi();return Vv(i)?(d.presentationPreparing=!1,Mn.visible=!1,Sc(!0),H["render-status"].textContent=d.standardRenderStatusText,d.cameraDirty=!0,!0):!1}function hM(){Sc(!1),Mn.visible=!0;const i=Xh();if(d.navigationGeometryContentSignature===i&&Mn.children.length>0){d.geometryRenderSignature=Ur(),Me.render(Ae,q),d.cameraDirty=!1;return}Wt(Mn);const e=d.data.geometry.primitives.filter(kl),t=new Map;for(const n of e){const r=n.primitive_type==="mesh"?"box":n.primitive_type,s=`${r}|${n.semantic_class}|${r==="path_mesh"?n.id:""}`;t.has(s)||t.set(s,{entries:[],primitiveType:r,semantic:n.semantic_class}),t.get(s).entries.push(n)}for(const n of t.values()){const r=new Kn({color:Pr[n.semantic]||9085852,fog:!0}),s=new bs(Nh(n.primitiveType,"",n.entries[0]),r,n.entries.length);s.userData.entries=n.entries,n.entries.forEach((a,o)=>s.setMatrixAt(o,Ns(a))),s.instanceMatrix.needsUpdate=!0,s.computeBoundingSphere(),Mn.add(s)}d.visiblePrimitives=e,d.navigationGeometryContentSignature=i,d.geometryRenderSignature=Ur(),d.geometryRebuildCount+=1,H["metric-primitives"].textContent=e.length.toLocaleString(),H["render-status"].textContent=`${e.length.toLocaleString()} / ${d.data.geometry.primitives.length.toLocaleString()} primitives · ${t.size} proxy groups · navigation`,Me.render(Ae,q),d.cameraDirty=!1}const Ja=new ja(.5,.5,1,12,1,!1);Ja.rotateX(Math.PI/2);const wc=new lc(.5,1);function Nh(i,e="",t=null,n={}){if(i==="path_mesh"&&t){const r=new yt,s=t.metadata.mesh_vertices;r.setAttribute("position",new mt(s.flat(),3)),r.setIndex(t.metadata.mesh_triangles.flat());const a=Number(n.texture_scale_m||4),o=s.flatMap(([l,c])=>[(l*t.size.x+t.center.x)/a,(c*t.size.y+t.center.y)/a]);return r.setAttribute("uv",new mt(o,2)),r.setAttribute("uv1",r.getAttribute("uv")),r.setAttribute("uv2",r.getAttribute("uv")),r.computeVertexNormals(),r}return i==="cylinder"?Ja:i==="sphere"?wc:e?pM(e):Zt}function fM(i,e){const t=Number(e?.texture_scale_m||0);if(i.primitive_type!=="box"||t<=0)return"";const n=r=>Math.max(.5,Math.round(r/t*2)/2);return[n(i.size.x),n(i.size.y),n(i.size.z)].join(",")}function pM(i){if(Aa.has(i))return Aa.get(i);const[e,t,n]=i.split(",").map(Number),r=Zt.clone(),s=r.getAttribute("uv");return[[t,n],[t,n],[e,n],[e,n],[e,t],[e,t]].forEach(([o,l],c)=>{for(let h=c*4;h<c*4+4;h+=1)s.setXY(h,s.getX(h)*o,s.getY(h)*l)}),s.needsUpdate=!0,r.setAttribute("uv1",s),r.setAttribute("uv2",s),Aa.set(i,r),r.userData.citygSharedGeometry=!0,r}function Mu(i,e,t,n=null){const r=d.data?.raw?.config?.material_textures?.[e];if(!r)return;const s=d.data?.raw?.config?.texture_base||"/texture/",a=(o,l)=>{const c=r[o];if(!c)return;const h=`${s.endsWith("/")?s:`${s}/`}${encodeURIComponent(c)}`;d.materialTextureUrls.add(h),Bv({promises:bh,ready:tM,owned:yc,states:xc,load:u=>Qv.loadAsync(u)},h,u=>{i.userData.citygDisposed||(u.wrapS=_i,u.wrapT=_i,o==="base_color"&&(u.colorSpace=Et),n?n(o,u):l(u),i.needsUpdate=!0,d.cameraDirty=!0)})};a("base_color",o=>{i.map=o}),a("normal",o=>{i.normalMap=o}),a("roughness",o=>{i.roughnessMap=o}),a("ambient_occlusion",o=>{i.aoMap=o,i.aoMapIntensity=.72})}let Ca=Promise.resolve(),dn="idle",Pa=0;function Ms(i){const e=Ev(d.mode,d.daylight,Bt[d.renderProfile],d.skyPreset,i?.sky_presets)?i.sky_presets[d.skyPreset]:null,t=e?.file||i?.environment_file,n=i?.environment_base||"/environment/";return{preset:e,filename:t,url:t?`${n.endsWith("/")?n:`${n}/`}${encodeURIComponent(t)}`:""}}function Ec(i){if(d.contextLost)return;if(!Bt[d.renderProfile].environment){Ae.environment=null;return}if(d.mode==="room"&&d.data?.geometry.metadata?.room_studio_environment===!0){if(!ds){const n=new av;ds=vs.fromScene(n,.04),n.dispose()}Ae.environment=ds.texture,Ae.environmentIntensity=.65,dn="ready";return}const{url:e}=Ms(i);if(!e){Ae.environment=null,dn="idle";return}if(Mr.has(e)){as=e,vr=Mr.get(e).target,dn="ready",Ae.environment=vr.texture;return}if(e===as&&dn==="pending")return Ca;as=e,dn="pending";const t=Pa;return Ae.environment=null,Ca=(async()=>{try{os.has(e)||os.set(e,(async()=>{const r=await eM.loadAsync(e);if(d.contextLost||t!==Pa)throw r.dispose(),new Error("WebGL context unavailable");r.mapping=La;const s=Tv(r),a=vs.fromEquirectangular(r),o={source:r,target:a,analysis:s};return Mr.set(e,o),o})());const n=await os.get(e);if(e!==Ms(d.data?.raw.config).url||!Bt[d.renderProfile].environment)return;vr=n.target,dn="ready",Ae.environment=n.target.texture,Ps(),d.cameraDirty=!0}catch(n){if(t!==Pa||(os.delete(e),e!==as))return;dn="failed",console.warn("CityG: failed to load HDR environment",n)}})(),Ca}function ya(i){if(d.renderProfile==="navigation")return!1;const e=i.primitive_type==="mesh"&&i.metadata?.resolved_asset&&!!i.metadata?.asset_id;if(wh(i))return!0;if(!e||d.renderProfile!=="review")return e;if(["room","floor","floor_plan"].includes(d.mode))return!0;if(!["road","landscape","building_exterior"].includes(d.observationKind))return!1;const t=d.data.hierarchy.entities.get(i.owner_id),n=new Set([i.owner_id,...t?d.data.hierarchy.lineage(i.owner_id):[]]);if(cv(n,d.observationTargetIds,d.data.hierarchy.entities,i.metadata))return!0;if(d.observationKind==="building_exterior"){const r=[...d.observationTargetIds].find(s=>d.data.hierarchy.entities.get(s)?.type==="building");return!!(r&&t?.buildingId===r)}return!1}function fr(i,e){let t=2166136261;for(let n=0;n<i.length;n+=1)t^=i.charCodeAt(n),t=Math.imul(t,16777619);return(t>>>0)%e}function xn(i){if(d.renderProfile==="prototype_capture"&&Mh(i)&&d.prototypeCaptureAssetIds&&!d.prototypeCaptureAssetIds.has(i.id)||d.mode==="overview"&&d.highFidelityOverview&&!fn(d.renderProfile)&&i.metadata?.resolved_asset&&!wh(i))return!1;if(d.renderProfile!=="review"||["room","floor","floor_plan"].includes(d.mode))return!0;const e=d.data.hierarchy.entities.get(i.owner_id),t=d.data.layerMap.get(i.layer_id)?.layer_type||"unknown",n=[...d.observationTargetIds].filter(o=>d.data.hierarchy.entities.get(o)?.type==="building"),r=n.length===1?n[0]:null,s=!!(r&&e?.buildingId===r);if(!["roads","building_shell","district","root"].includes(t))return!1;const a=i.semantic_class;return t!=="building_shell"?!0:a==="facade_asset_window"||a==="window_backing"?s:["facade_window","curtain_wall_glass"].includes(a)?a==="curtain_wall_glass"?!0:!!d.streaming||s||fr(i.id,8)===0:["facade_frame","facade_fin","facade_spandrel_band","facade_zone_band","mechanical_louver","balcony_rail"].includes(a)?s||fr(i.id,5)===0:!0}const mM=new Set(["river_water","river_bank","river_promenade","riparian_green","bridge_deck","bridge_parapet","bridge_railing","bridge_abutment","parcel_ground","road_surface","junction_surface","sidewalk","curb","lane_marking","crosswalk","road_median","bicycle_lane_surface","stop_line","city_ground","parcel_surface_patch","parcel_edge","landscape_path","plaza","grass","landscape_patch"]),gM=new Set(["exterior_wall","roof","roof_parapet","roof_monitor","floor_slab","facade_ground_band","entrance_portal","curtain_wall_glass"]),_M=new Set(["floor_slab","interior_wall","door"]),yM=new Map([["street_tree_asset",5],["park_tree_asset",5],["parcel_tree_asset",6],["street_light_asset",5],["vehicle_asset",10],["pedestrian_asset",18],["street_bench",8],["bench",10]]);function xM(i,e){if(d.renderProfile!=="navigation")return!0;const t=i.semantic_class;if(i.metadata?.resolved_asset||i.primitive_type==="mesh"){const n=yM.get(t);return!!(n&&fr(i.id,n)===0)}return e==="roads"||e==="district"||e==="root"?mM.has(t)?["lane_marking","crosswalk","bicycle_lane_surface","parcel_surface_patch"].includes(t)?fr(i.id,t==="parcel_surface_patch"?2:3)===0:!0:!1:e==="building_shell"?gM.has(t)?!0:t==="facade_window"?!!d.streaming||fr(i.id,10)===0:["facade_frame","facade_fin","balcony_rail"].includes(t)?fr(i.id,18)===0:!1:e==="floor"?_M.has(t):!1}function us(i,e=d.data?.hierarchy.entities.get(i.owner_id)){if(!e||!d.floorId)return!1;if(e.floorId===d.floorId)return!0;if(e.type==="vertical_connector"){const s=d.data?.hierarchy.entities.get(d.floorId)?.entity,a=d.data?.hierarchy.entities.get(d.floorId);if(!a?.buildingId||e.buildingId!==a.buildingId)return!1;if(i.semantic_class==="stair_tread"&&i.metadata?.from_level!==void 0)return Number(s?.level)===Number(i.metadata.from_level);if(i.metadata?.served_level!==void 0)return Number(s?.level)===Number(i.metadata.served_level);if(i.semantic_class==="elevator_cabin"||i.semantic_class==="elevator_cabin_door"){const o=i.metadata?.state_machine_id,l=o?d.doorStates.get(o):null,c=String(l||"").replace("level_","");return Number(s?.level)===Number(c)}return e.floorIds?.includes(d.floorId)||!1}const t=i.metadata?.served_level;return t===void 0||!e.buildingId?!1:(d.data?.hierarchy.entities.get(e.buildingId)?.entity?.floors||[]).find(s=>Number(s.level)===Number(t))?.id===d.floorId}function vM(i){const e=d.data?.raw?.config||{},t=e.asset_base||"/asset/",n=e.asset_files?.[i]||`${i}.glb`;return`${t.endsWith("/")?t:`${t}/`}${encodeURIComponent(n)}`}async function bu(i){return kr.get(i)}function Uh(){return fn(d.renderProfile)&&["overview","full"].includes(d.mode)&&q.position.z-we.target.z>500?1/0:160}function MM(i){const e=d.assetRenderGeneration,t=new Map(Ol),n=new Set(Bl),r=fn(d.renderProfile),s=new Map;for(const u of i){const f=t.get(u.id)||u.metadata.asset_id;s.set(f,JSON.stringify([vM(f),Wv(Ta.get(f)??1/0)]))}kr.retain(s.values());const a={generation:e,expected:i.length,pending:i.length,loaded:0,cached:0,fallback:0,failed:0,errors:[],ready:i.length===0};if(d.assetLoadState=a,!i.length){d.assetReadyPromise=Promise.resolve({...a});return}const o=new Map,l=Uh();for(const u of i){const f=`${t.get(u.id)||u.metadata.asset_id}|scoped:${Ia(u)}|${vh(u,l)}|shadow:${!r||n.has(u.id)}`;o.has(f)||o.set(f,[]),o.get(f).push(u)}const c=async u=>{const f=t.get(u.id)||u.metadata.asset_id,p=Ia(u),_=`${u.id}|${f}|xray:${d.xray?1:0}|scope:${p?JSON.stringify(d.hierarchyDisplay):"none"}`;try{if(d.assetObjectCache.has(_)){if(e!==d.assetRenderGeneration||!d.data)return;Qn.add(d.assetObjectCache.get(_)),a.loaded+=1,a.cached+=1;return}const y=await bu(s.get(f));if(e!==d.assetRenderGeneration||!d.data)return;const g=y.clone(!0);g.position.set(u.center.x,u.center.y,u.center.z),g.rotation.z=wn.degToRad(u.rotation_z_deg||0),g.scale.set(u.size.x,u.size.y,u.size.z),g.userData.entry=u,g.traverse(m=>{if(m.isMesh&&(m.userData.entry=u,m.castShadow=!r||n.has(u.id),m.receiveShadow=!0,d.xray||p)){const E=Array.isArray(m.material)?m.material.map(w=>Su(w,p)):[Su(m.material,p)];m.material=Array.isArray(m.material)?E:E[0],m.userData.citygOwnedMaterials=E}}),d.assetObjectCache.set(_,g),Qn.add(g),e===d.assetRenderGeneration&&(a.loaded+=1)}catch(y){if(e===d.assetRenderGeneration){console.warn(`CityG: failed to load GLB asset ${f}`,y),a.errors.length<32&&a.errors.push({asset_id:f,primitive_id:u.id,reason:String(y?.message||y).slice(0,500)});try{SM(u),a.fallback+=1}catch(g){console.warn(`CityG: failed to create fallback for ${f}`,g),a.failed+=1}}}finally{e===d.assetRenderGeneration&&(a.pending=Math.max(0,a.pending-1))}},h=Gv([...o.values()],async u=>{const f=t.get(u[0].id)||u[0].metadata.asset_id;if(!d.xray&&!Ia(u[0]))try{const p=await bu(s.get(f));if(e!==d.assetRenderGeneration||!d.data)return;const _=dv(p,u,Ns);if(_){const y=!r||u.some(g=>n.has(g.id));for(const g of _)g.castShadow=y,Qn.add(g);a.loaded+=u.length,a.pending-=u.length;return}}catch{}for(const p of u){if(e!==d.assetRenderGeneration)return;await c(p)}},()=>e===d.assetRenderGeneration&&!d.contextLost);d.assetReadyPromise=h.then(()=>(e===d.assetRenderGeneration&&(a.pending=0,a.ready=a.failed===0,Ga(),d.cameraDirty=!0),{...a,ready:e===d.assetRenderGeneration&&a.ready}))}function Ia(i){return yh(d.hierarchyDisplay,d.data.hierarchy.entities.get(i.owner_id),d.data.layerMap.get(i.layer_id)?.layer_type)}function bM(){if(!d.presentationFocusId)return;const i=d.presentationFocusId,e=new kt;for(const n of d.visiblePrimitives){const r=d.data.hierarchy.entities.get(n.owner_id);(n.owner_id===i||r?.floorId===i||r?.roomId===i||n.metadata?.room_ids?.includes(i))&&Ac(e,n)}if(e.isEmpty())return;const t=new ah(e,14250024);t.material.depthTest=!1,t.material.toneMapped=!1,t.renderOrder=100,Cs.add(t)}function Fh(){const i=d.hierarchyDisplay?.cut_above_m;return Number.isFinite(i)?[new jn(new P(0,0,-1),i)]:[]}function Su(i,e=!1){const t=i.clone();return t.transparent=!0,t.opacity=e?d.hierarchyDisplay.shell_opacity:Math.min(t.opacity??1,.24),t.clippingPlanes=e?Fh():[],t.depthWrite=!1,t}function SM(i){const e=new Dn({color:Pr[i.semantic_class]||9085852,roughness:.78,transparent:d.xray,opacity:d.xray?.2:1}),t=new ut(Zt,e);t.matrixAutoUpdate=!1,t.matrix.copy(Ns(i)),t.userData.entry=i,t.userData.citygOwnedMaterials=[e],t.castShadow=!0,t.receiveShadow=!0,Qn.add(t)}function kl(i){if(zi?.suppressed(i.id)||i.semantic_class==="collision_envelope"||i.metadata?.viewer_room_only&&d.mode!=="room"||!d.enabledSemantics.has(i.semantic_class))return!1;const e=d.data.hierarchy.entities.get(i.owner_id);if(d.districtId!=="all"&&e?.districtId&&e.districtId!==d.districtId)return!1;const t=d.data.layerMap.get(i.layer_id)?.layer_type||"unknown";if(!xM(i,t))return!1;if(d.hierarchyDisplay&&["overview","building","full"].includes(d.mode))return fv(d.hierarchyDisplay,e,t,us(i,e))&&xn(i);if(d.mode==="room"){if(!Za(d.roomId)||i.metadata?.room_ceiling&&d.roomCameraPreset!=="eye")return!1;if(d.roomCameraPreset==="cutaway"&&(["interior_wall","door"].includes(i.semantic_class)||i.metadata?.support_kind==="wall")){const n=Ds(d.roomId);if(n){const r=i.center.x-n.centerX,s=i.center.y-n.centerY,a=r*Math.cos(n.rotation)+s*Math.sin(n.rotation),o=-r*Math.sin(n.rotation)+s*Math.cos(n.rotation);if(a>n.width*.32||o<-n.depth*.32)return!1}}return e?.roomId===d.roomId||d.data.hierarchy.lineage(i.owner_id).includes(d.roomId)||Array.isArray(i.metadata?.room_ids)&&i.metadata.room_ids.includes(d.roomId)||e?.type==="door"&&e.roomIds?.includes(d.roomId)?xn(i):!1}if(d.mode==="overview")return["roads","building_shell","district","root"].includes(t)&&xn(i);if(d.mode==="building")return d.autoCutaway&&e?.buildingId===d.buildingId&&t==="building_shell"&&(["roof","roof_monitor"].includes(i.semantic_class)||i.metadata?.roof_system)?!1:(["roads","building_shell","district","root"].includes(t)||e?.buildingId===d.buildingId)&&xn(i);if(d.mode==="floor"){if(d.autoCutaway&&e?.buildingId===d.buildingId&&t==="building_shell"&&(["roof","roof_monitor"].includes(i.semantic_class)||i.metadata?.roof_system))return!1;if(t==="building_shell"){const n=e?.buildingId===d.buildingId,r=e?.floorId===d.floorId,s=e?.type==="building";return n&&(r||s&&i.semantic_class==="exterior_wall")?xn(i):!1}return us(i,e)&&xn(i)}return d.mode==="floor_plan"?us(i,e)&&xn(i):xn(i)}function Tc(){const i=new Map;for(const e of d.data.geometry.primitives){if(e.semantic_class==="collision_envelope")continue;const t=d.data.hierarchy.entities.get(e.owner_id),n=d.data.layerMap.get(e.layer_id)?.layer_type;t?.type!=="building"||n!=="building_shell"||d.districtId!=="all"&&t.districtId!==d.districtId||(i.has(e.owner_id)||i.set(e.owner_id,new kt),Ac(i.get(e.owner_id),e))}return i}function Ac(i,e){const t=wn.degToRad(e.rotation_z_deg||0),n=(Math.abs(Math.cos(t))*e.size.x+Math.abs(Math.sin(t))*e.size.y)/2,r=(Math.abs(Math.sin(t))*e.size.x+Math.abs(Math.cos(t))*e.size.y)/2;i.expandByPoint(new P(e.center.x-n,e.center.y-r,e.center.z-e.size.z/2)),i.expandByPoint(new P(e.center.x+n,e.center.y+r,e.center.z+e.size.z/2))}function Oh(i){const e=new kt;for(const t of d.data.geometry.primitives){if(t.semantic_class==="collision_envelope")continue;const n=d.data.hierarchy.entities.get(t.owner_id);i(n,t)&&Ac(e,t)}return e}function Ds(i){const e=d.data?.hierarchy.entities.get(i),t=e?.entity,n=d.data?.hierarchy.entities.get(e?.floorId)?.entity;if(!t?.bounds||!n)return null;const r=d.data.hierarchy.entities.get(e.buildingId)?.entity,s=Number(r?.metadata?.orientation_deg||0),a=wn.degToRad(s),o=Math.cos(a),l=Math.sin(a);let c=1/0,h=1/0,u=-1/0,f=-1/0,p=0;for(const _ of d.data.geometry.primitives){if(_.semantic_class!=="interior_wall"||!Array.isArray(_.metadata?.room_ids)||!_.metadata.room_ids.includes(i))continue;p+=1;const y=wn.degToRad(Number(_.rotation_z_deg||0)),g=Math.cos(y),m=Math.sin(y);for(const E of[-.5,.5])for(const w of[-.5,.5]){const x=g*E*_.size.x-m*w*_.size.y,T=m*E*_.size.x+g*w*_.size.y,L=_.center.x+x,C=_.center.y+T,R=L*o+C*l,v=-L*l+C*o;c=Math.min(c,R),u=Math.max(u,R),h=Math.min(h,v),f=Math.max(f,v)}}if(p===0)return null;if(u-c>.5&&f-h>.5){const _=(c+u)/2,y=(h+f)/2;return{centerX:_*o-y*l,centerY:_*l+y*o,width:u-c,depth:f-h,rotation:a,elevation:Number(n.elevation_m||0),height:Math.max(.06,Number(t.height_m||n.height_m||3)),source:"realized_walls"}}return null}function wM(){if(!d.data||!d.roomId)return;const i=d.data.hierarchy.entities.get(d.roomId);if(!i||i.type!=="room")return;const e=i.entity,n=d.data.hierarchy.entities.get(i.floorId)?.entity;if(!e.bounds||!n)return;const r=Ds(d.roomId);if(!r)return;if(!(d.data.geometry.primitives.some(y=>y.metadata?.room_floor_finish&&y.metadata?.room_ids?.includes(d.roomId))&&d.appearanceMode==="presentation")){const y=new Dn({color:d.appearanceMode==="presentation"?{warm:8740925,minimal:10920857,industrial:6448230}[e.metadata?.room_design?.palette]||12104615:7128484,transparent:d.appearanceMode!=="presentation",opacity:d.appearanceMode==="presentation"?1:.14,depthWrite:d.appearanceMode==="presentation",side:un}),g=new ut(Zt,y);g.position.set(r.centerX,r.centerY,r.elevation+.025),g.rotation.z=r.rotation,g.scale.set(r.width,r.depth,.05),g.renderOrder=8,Lr.add(g)}if(d.appearanceMode==="presentation"&&!d.showOutlines)return;const a=r.width/2,o=r.depth/2,l=[[-a,-o],[a,-o],[a,-o],[a,o],[a,o],[-a,o],[-a,o],[-a,-o]],c=Math.cos(r.rotation),h=Math.sin(r.rotation),u=r.elevation+Math.min(.12,r.height*.08),f=[];for(const[y,g]of l)f.push(r.centerX+y*c-g*h,r.centerY+y*h+g*c,u);const p=new yt;p.setAttribute("position",new mt(f,3));const _=new ni(p,new Fn({color:9106118,transparent:!0,opacity:.95,depthTest:!1}));_.renderOrder=18,Lr.add(_)}const EM={corridor:9676714,lobby:6273224,reception:7325344,office:8166374,open_office:8825324,meeting_room:11111382,living_room:14260837,bedroom:13928090,kitchen:14728547,bathroom:7191508,shop:14781025,storage:10328973,service_room:9280646};function wu(i,e){return new Kn({color:i,transparent:!0,opacity:e,depthWrite:!1,side:un})}function TM(){if(!d.data||!d.floorId||!["floor","floor_plan"].includes(d.mode))return;const i=d.data.hierarchy.entities.get(d.floorId),e=d.data.hierarchy.entities.get(d.buildingId),t=i?.entity,n=e?.entity;if(!t||!n)return;for(const s of t.rooms||[]){const a=Ds(s.id);if(!a)continue;const o=EM[s.function]||8232856,l=new ut(Zt,wu(o,d.mode==="floor_plan"?.16:.07));if(l.position.set(a.centerX,a.centerY,a.elevation+.055),l.rotation.z=a.rotation,l.scale.set(a.width*.96,a.depth*.96,.025),l.renderOrder=7,Yn.add(l),d.showLabels){const c=Hl(s.name||s.id,String(s.function||"room").replaceAll("_"," ")),h=Math.max(2.8,Math.min(6.5,Math.min(a.width,a.depth)*.42));c.scale.set(h,h*.29,1),c.position.set(a.centerX,a.centerY,a.elevation+Math.max(.18,a.height*.08)),c.renderOrder=26,Yn.add(c)}}const r=Number(t.level);for(const s of n.vertical_connectors||[]){if(r<Number(s.from_level)||r>Number(s.to_level))continue;const a=s.bounds;if(!a)continue;const o=Number(a.max_x)-Number(a.min_x),l=Number(a.max_y)-Number(a.min_y),c=s.connector_type==="elevator",h=c?15317083:9403361,u=new ut(Zt,wu(h,d.mode==="floor_plan"?.22:.12));u.position.set(a.min_x+o/2,a.min_y+l/2,t.elevation_m+.11),u.scale.set(o,l,.06),u.renderOrder=11,Yn.add(u);const f=new ni(new eh(Zt),new Fn({color:h,transparent:!0,opacity:.95,depthTest:!1}));if(f.position.copy(u.position),f.scale.set(o,l,.06),f.renderOrder=24,Yn.add(f),d.showLabels){const p=Hl(c?"Vertical core":"Fire stairs",c?"elevator":"stairs"),_=Math.max(3.2,Math.min(6.2,Math.max(o,l)*1.5));p.scale.set(_,_*.29,1),p.position.set(u.position.x,u.position.y,t.elevation_m+Math.max(.3,t.height_m*.15)),p.renderOrder=27,Yn.add(p)}}}function AM(){if(!d.enabledSemantics.has("road_surface"))return;const i=[];for(const n of d.data.geometry.primitives){if(n.semantic_class!=="road_surface")continue;const r=wn.degToRad(n.rotation_z_deg||0),s=n.size.x*.47,a=Math.cos(r)*s,o=Math.sin(r)*s,l=n.center.z+n.size.z/2+.07;i.push(n.center.x-a,n.center.y-o,l,n.center.x+a,n.center.y+o,l)}const e=new yt;e.setAttribute("position",new mt(i,3));const t=new ni(e,new Yp({color:d.daylight?16774064:16770442,dashSize:4.5,gapSize:3,transparent:!0,opacity:d.daylight?.9:.72,depthTest:!1}));t.computeLineDistances(),t.renderOrder=12,Ts.add(t)}function RM(){for(const[i,e]of Tc()){if(e.isEmpty())continue;const t=i===d.buildingId&&["building","floor"].includes(d.mode),n=new ah(e,t?16767083:d.daylight?3235674:8640177);n.material.transparent=!0,n.material.opacity=t?.95:.56,n.material.depthTest=!1,n.renderOrder=14,As.add(n)}}function CM(){for(const[i,e]of Tc()){if(["building","floor"].includes(d.mode)&&i!==d.buildingId)continue;const t=d.data.hierarchy.entities.get(i);if(!t||e.isEmpty())continue;const n=Hl(t.entity.name||i,`${t.entity.function||"building"} · ${(t.entity.floors||[]).length}F`),r=e.getCenter(new P),s=e.getSize(new P),a=Math.max(15,Math.min(28,Math.max(s.x,s.y)*.72));n.scale.set(a,a*.29,1),n.position.set(r.x,r.y,e.max.z+Math.max(3.5,s.z*.12)),n.renderOrder=30,Rs.add(n)}}function Hl(i,e){const t=document.createElement("canvas");t.width=512,t.height=144;const n=t.getContext("2d");n.fillStyle=d.daylight?"rgba(9, 30, 28, 0.86)":"rgba(4, 15, 14, 0.9)",n.fillRect(6,6,500,132),n.fillStyle="#72e3b2",n.fillRect(6,6,10,132),n.fillStyle="#f2faf7",n.font="600 42px system-ui, sans-serif",n.textBaseline="middle",n.fillText(String(i).slice(0,23),36,59),n.fillStyle="#a7c0b9",n.font="600 24px system-ui, sans-serif",n.fillText(String(e).replaceAll("_"," ").toUpperCase().slice(0,32),36,105);const r=new Wp(t);r.colorSpace=Et,r.minFilter=Tt;const s=new Ku({map:r,transparent:!0,depthTest:!1,depthWrite:!1});return new Up(s)}function PM(i){return d.data.errorIds.has(i.owner_id)?!0:d.data.hierarchy.lineage(i.owner_id).some(e=>d.data.errorIds.has(e))}function Ns(i){let e=wn.degToRad(i.rotation_z_deg||0),t=i.center.x,n=i.center.y,r=i.center.z;const s=i.metadata?.state_machine_id,a=d.data?.interactions?.state_machines?.find(c=>c.id===s),o=s?d.doorStates.get(s):null;if(a?.state_type==="elevator_controller"){const c=a.states?.[o]?.cabin_z_m;c!==void 0&&(r=i.metadata?.transport_elevator_version===1?r+c-i.metadata.cabin_initial_floor_z_m:c)}else s&&o==="open"&&({x:t,y:n,z:r,angle:e}=_h(i,i.metadata.upper_limit_deg??90));const l=new De;return l.compose(new P(t,n,r),new En().setFromAxisAngle(new P(0,0,1),e),new P(i.size.x,i.size.y,i.size.z)),l}function Wt(i){for(const e of[...i.children]){gc(e);for(const t of[e.material].flat().filter(Boolean))t.userData.citygDisposed=!0,zv(t,yc),t.dispose();e.geometry&&!e.geometry.userData.citygSharedGeometry&&![Zt,Ja,wc].includes(e.geometry)&&e!==nn&&e.geometry.dispose(),i.remove(e)}}function Rc(){d.assetRenderGeneration+=1,d.assetLoadState={generation:d.assetRenderGeneration,expected:0,pending:0,loaded:0,fallback:0,cached:0,failed:0,ready:!0},d.assetReadyPromise=Promise.resolve({...d.assetLoadState});for(const i of[...Qn.children])gc(i),i.traverse(e=>{for(const t of e.userData.citygOwnedMaterials||[])t.dispose();delete e.userData.citygOwnedMaterials}),Qn.remove(i);d.assetObjectCache.clear()}function Bh(){Rc();for(const i of[Li,Ir,Ui,Ts,As,Rs,Lr,Yn,Cs])Wt(i);d.standardGeometryContentSignature="",d.standardVisiblePrimitives=[],d.data&&(d.data.groundEdgePrimitives=null,d.data.depthPrimitives=null),kr.retain([]),Me.renderLists.dispose()}function IM(){const i=d.data.navigation,e=new Map(i.nodes.map(a=>[a.id,a])),t=[];for(const a of i.edges){const o=e.get(a.start_node_id),l=e.get(a.end_node_id);!o||!l||t.push(o.position.x,o.position.y,o.position.z+.18,l.position.x,l.position.y,l.position.z+.18)}const n=new yt;n.setAttribute("position",new mt(t,3)),Ir.add(new ni(n,new Fn({color:4640161,transparent:!0,opacity:.5,depthTest:!1})));const r=i.nodes.flatMap(a=>[a.position.x,a.position.y,a.position.z+.22]),s=new yt;s.setAttribute("position",new mt(r,3)),Ir.add(new Ju(s,new ac({color:12713961,size:2.2,sizeAttenuation:!0,depthTest:!1})))}function LM(){if(!d.selectedPrimitive)return;const i=d.data.navigation,e=new Map(i.nodes.map(p=>[p.id,p])),t=i.nodes.filter(p=>p.node_type==="outdoor_junction"),n=new Set(d.data.hierarchy.lineage(d.selectedPrimitive.owner_id)),r=i.nodes.find(p=>p.owner_id===d.selectedPrimitive.owner_id)||i.nodes.find(p=>n.has(p.owner_id))||i.nodes.find(p=>d.data.hierarchy.lineage(p.owner_id).includes(d.selectedPrimitive.owner_id));if(!t.length||!r)return Pt("No navigation node belongs to this selection");const s=new Map;for(const p of i.edges)s.has(p.start_node_id)||s.set(p.start_node_id,[]),s.has(p.end_node_id)||s.set(p.end_node_id,[]),s.get(p.start_node_id).push({id:p.end_node_id,edge:p}),s.get(p.end_node_id).push({id:p.start_node_id,edge:p});const a=t[0].id,o=[a],l=new Map([[a,null]]);for(;o.length&&!l.has(r.id);){const p=o.shift();for(const _ of s.get(p)||[])l.has(_.id)||(l.set(_.id,{node:p,edge:_.edge}),o.push(_.id))}if(!l.has(r.id))return Pt("No route found");const c=[];let h=r.id;for(;h;)c.push(h),h=l.get(h)?.node||null;c.reverse();const u=[];for(let p=0;p<c.length-1;p++){const _=e.get(c[p]).position,y=e.get(c[p+1]).position;u.push(_.x,_.y,_.z+.5,y.x,y.y,y.z+.5)}Wt(Ui);const f=new yt;f.setAttribute("position",new mt(u,3)),Ui.add(new ni(f,new Fn({color:16770669,linewidth:3,depthTest:!1}))),Pt(`Route: ${c.length} nodes · interactive doors allowed`)}function Ga(){if(!d.selectedPrimitive||!d.visiblePrimitives.some(t=>t.id===d.selectedPrimitive.id)){nn.visible=!1;return}const i=d.selectedPrimitive;Ns(i).decompose(nn.position,nn.quaternion,nn.scale),nn.scale.multiplyScalar(1.035),nn.visible=!0}function Gl(i,e=!1){d.cameraDirty=!0,d.selectedPrimitive=i,Nr(),Ga(),e&&kh(i)}function Nr(){const i=d.selectedPrimitive;if(H["empty-inspector"].hidden=!!i,H.inspector.hidden=!i,!i)return;const e=d.data.hierarchy.entities.get(i.owner_id);H["entity-type"].textContent=e?.type||i.semantic_class,H["entity-id"].textContent=i.owner_id;const t={primitive:i.id,semantic:i.semantic_class,layer:i.layer_id,material:i.material_id,body:i.body_type,size:`${lr(i.size.x)} × ${lr(i.size.y)} × ${lr(i.size.z)} m`,position:`${lr(i.center.x)}, ${lr(i.center.y)}, ${lr(i.center.z)}`,district:e?.districtId,building:e?.buildingId,floor:e?.floorId,function:e?.entity?.function};H["entity-properties"].replaceChildren(...Object.entries(t).filter(([,r])=>r!==void 0).map(([r,s])=>{const a=document.createElement("div"),o=document.createElement("dt");o.textContent=r;const l=document.createElement("dd");return l.textContent=s,a.append(o,l),a}));const n=i.metadata?.state_machine_id;if(H["door-button"].hidden=!n,n){const r=d.data.interactions.state_machines.find(s=>s.id===n);H["door-button"].textContent=r?.state_type==="elevator_controller"?`Move elevator · ${d.doorStates.get(n)?.replace("level_","L")}`:d.doorStates.get(n)==="open"?"Close door":"Open door"}H["route-button"].hidden=!DM(i.owner_id)}function DM(i){return d.data.navigation.nodes.length?d.data.navigation.nodes.some(e=>e.owner_id===i||d.data.hierarchy.lineage(e.owner_id).includes(i)):!1}function NM(){const i=d.data.issues,e=i.filter(t=>t.severity==="error");H["validation-summary"].className=`validation-summary ${e.length?"fail":"ok"}`,H["validation-summary"].textContent=e.length?`${e.length} errors · ${i.length-e.length} warnings`:`All ${i.length?"loaded reports":"checks"} passed`,H["validation-list"].replaceChildren(...i.slice(0,40).map(t=>{const n=document.createElement("div");n.className=`issue ${t.severity}`;const r=document.createElement("strong");r.textContent=t.code;const s=document.createElement("span");return s.textContent=t.message,n.append(r,s),n.addEventListener("click",()=>zh(t.entity_id)),n}))}function zh(i){const e=d.data.geometry.primitives.find(t=>t.owner_id===i)||d.data.geometry.primitives.find(t=>d.data.hierarchy.lineage(t.owner_id).includes(i));if(!e)return Pt(`No geometry found for ${i}`);Gl(e,!0)}function kh(i){const e=Math.max(i.size.x,i.size.y,i.size.z)*4+10,t=new P(i.center.x,i.center.y,i.center.z);we.target.copy(t),q.up.set(0,0,1),q.position.copy(t).add(new P(e,-e,e*.8)),we.update()}function UM(i){if(!i||i.isEmpty())return!1;const e=i.getCenter(new P),t=i.getSize(new P),n=Math.max(t.x,t.y,t.z*2.2)*1.35+8;return we.target.copy(e),q.up.set(0,0,1),q.position.copy(e).add(new P(n*.72,-n*.8,n*.62)),q.near=Math.max(.05,n/1e3),q.far=Math.max(1e3,n*20),q.updateProjectionMatrix(),we.update(),!0}function Fi(i="iso"){if(!d.data)return;const e=d.data.geometry.primitives,t=new P(1/0,1/0,1/0),n=new P(-1/0,-1/0,-1/0);for(const l of e)t.x=Math.min(t.x,l.center.x-l.size.x/2),t.y=Math.min(t.y,l.center.y-l.size.y/2),t.z=Math.min(t.z,l.center.z-l.size.z/2),n.x=Math.max(n.x,l.center.x+l.size.x/2),n.y=Math.max(n.y,l.center.y+l.size.y/2),n.z=Math.max(n.z,l.center.z+l.size.z/2);const r=t.clone().add(n).multiplyScalar(.5),s=n.clone().sub(t),a=Math.max(s.x,s.y,s.z*4)*1.15,o=q.position.clone().sub(we.target);if(we.target.copy(r),i==="top")q.up.set(0,1,0),q.position.copy(r).add(new P(0,0,a*1.35));else if(i==="fit"){const l=o;l.lengthSq()<1e-6&&l.set(a*.75,-a*.8,a*.68),l.normalize().multiplyScalar(a),q.position.copy(r).add(l)}else q.up.set(0,0,1),q.position.copy(r).add(new P(a*.75,-a*.8,a*.68));q.near=Math.max(.1,a/1e3),q.far=a*10,q.updateProjectionMatrix(),we.update()}function Hh(){if(!d.data||!d.floorId)return;const i=Oh((a,o)=>us(o,a));if(i.isEmpty()){Pt("Selected floor has no visible geometry");return}const e=i.getCenter(new P),t=i.getSize(new P),n=Math.max(t.x/Math.max(q.aspect,.1),t.y),r=wn.degToRad(q.fov*.5),s=Math.max(8,n/(2*Math.tan(r))*1.22);we.target.copy(e),q.up.set(0,1,0),q.position.set(e.x,e.y,e.z+s),q.near=Math.max(.05,s/1e3),q.far=Math.max(1e3,s*20),q.updateProjectionMatrix(),we.update()}function Cc(){if(!d.data||!d.floorId)return!1;const i=Oh((r,s)=>us(s,r));if(i.isEmpty())return!1;const e=i.getCenter(new P),t=i.getSize(new P),n=Math.max(t.x,t.y,t.z*2.2)*1.18+5;return we.target.copy(e),q.up.set(0,0,1),q.position.copy(e).add(new P(n*.78,-n*.86,Math.max(5,n*.92))),q.near=Math.max(.05,n/1e3),q.far=Math.max(1e3,n*20),q.fov=52,q.updateProjectionMatrix(),we.update(),!0}function FM(){if(!d.data||!d.floorId)return!1;const i=d.data.hierarchy.entities.get(d.floorId)?.entity;if(!i)return!1;const t=(i.rooms||[]).filter(l=>l.function==="corridor").map(l=>({room:l,frame:Ds(l.id)})).filter(l=>l.frame).sort((l,c)=>{const h=l.frame.width*l.frame.depth;return c.frame.width*c.frame.depth-h})[0];if(!t)return Cc();const n=t.frame,s=n.width>=n.depth?new P(Math.cos(n.rotation),Math.sin(n.rotation),0):new P(-Math.sin(n.rotation),Math.cos(n.rotation),0),a=Math.max(2.4,Math.min(7,Math.max(n.width,n.depth)*.28)),o=new P(n.centerX,n.centerY,n.elevation+Math.min(1.65,n.height*.58));return we.target.copy(o).add(s.clone().multiplyScalar(Math.min(7,Math.max(2,a*1.8)))),q.up.set(0,0,1),q.position.copy(o).add(s.clone().multiplyScalar(-a)),q.position.z=o.z,q.fov=68,q.near=.03,q.far=Math.max(250,Math.max(n.width,n.depth)*30),q.updateProjectionMatrix(),we.update(),!0}function OM(){if(!d.data||!d.floorId||!d.buildingId)return!1;const i=d.data.hierarchy.entities.get(d.floorId)?.entity,e=d.data.hierarchy.entities.get(d.buildingId)?.entity;if(!i||!e)return!1;const t=Number(i.level),r=(e.vertical_connectors||[]).filter(c=>t>=Number(c.from_level)&&t<=Number(c.to_level)).sort((c,h)=>+(h.connector_type==="elevator")-+(c.connector_type==="elevator"))[0];if(!r?.bounds)return Cc();const s=Number(r.bounds.max_x)-Number(r.bounds.min_x),a=Number(r.bounds.max_y)-Number(r.bounds.min_y),o=new P(Number(r.bounds.min_x)+s/2,Number(r.bounds.min_y)+a/2,Number(i.elevation_m||0)+Math.max(.8,Number(i.height_m||3)*.42)),l=Math.max(4,Math.max(s,a)*4.2);return we.target.copy(o),q.up.set(0,0,1),q.position.copy(o).add(new P(l*.82,-l*.92,Math.max(3.2,l*.74))),q.fov=52,q.near=.03,q.far=Math.max(250,l*18),q.updateProjectionMatrix(),we.update(),!0}function Pc(i=d.floorCameraPreset){return i==="top"?Hh():i==="corridor"?FM():i==="core"?OM():Cc()}function Gh(i,{render:e=!0}={}){if(d.hierarchyDisplay=null,d.presentationFocusId=null,!d.buildingId||!d.floorId)return Pt("Select a building and floor first"),!1;if(!Object.prototype.hasOwnProperty.call(Eh,i))return!1;d.floorCameraPreset=i;const t=i==="top"?"floor_plan":"floor",n=d.mode!==t;return d.mode=t,H["mode-buttons"]&&H["mode-buttons"].querySelectorAll("button").forEach(r=>{r.classList.toggle("active",r.dataset.mode===d.mode)}),ii(),ri(),e&&n&&$e(),!!Pc(i)}function BM(){if(!d.data)return;const i=d.data.city.road_network?.segments||[];if(!i.length)return;const t=[...i].sort((h,u)=>{const f=_=>_.road_class==="collector"?2:_.road_class==="local"?1:0,p=_=>_.centerline.slice(1).reduce((y,g,m)=>y+Math.hypot(g.x-_.centerline[m].x,g.y-_.centerline[m].y),0);return f(u)-f(h)||p(u)-p(h)||h.id.localeCompare(u.id)})[0],n=t.centerline.slice(1).map((h,u)=>Math.hypot(h.x-t.centerline[u].x,h.y-t.centerline[u].y)),r=n.reduce((h,u)=>h+u,0),s=(h,u)=>{let f=Math.max(0,Math.min(r,h));for(let p=0;p<n.length;p++){if(f>n[p]&&p<n.length-1){f-=n[p];continue}const _=t.centerline[p],y=t.centerline[p+1],g=(y.x-_.x)/Math.max(1e-8,n[p]),m=(y.y-_.y)/Math.max(1e-8,n[p]);return{x:_.x+g*f-m*u,y:_.y+m*f+g*u}}return t.centerline[0]},a=Math.min(Math.max(8,r*.18),r-4),o=Number(t.width_m||10)*.22,l=s(a,o),c=s(a+Math.min(28,r*.35),o);q.position.set(l.x,l.y,1.7),we.target.set(c.x,c.y,1.58),q.up.set(0,0,1),q.fov=62,q.near=.05,q.far=Math.max(1e3,r*20),d.mode="overview",d.showOutlines=!1,d.showLabels=!1,H["outline-toggle"].checked=!1,H["labels-toggle"].checked=!1,q.updateProjectionMatrix(),we.update(),$e()}function Qa(){if(!d.data||!d.roomId)return!1;const i=d.data.hierarchy.entities.get(d.roomId);if(!i||i.type!=="room")return!1;const e=Ds(d.roomId);if(!e)return!1;if(d.roomCameraPreset!=="eye"){const u=Math.max(e.width,e.depth,3);if(we.target.set(e.centerX,e.centerY,e.elevation+.1),q.up.set(0,0,1),d.roomCameraPreset==="top"){const f=e.height+Math.max(e.width/Math.max(.1,q.aspect),e.depth)/(2*Math.tan(wn.degToRad(24)))*1.12;q.position.set(e.centerX,e.centerY-.001,e.elevation+f),q.up.set(-Math.sin(e.rotation),Math.cos(e.rotation),0)}else{we.target.z=e.elevation+e.height/2;const f=new P(1,-1,1.16).normalize().applyAxisAngle(new P(0,0,1),e.rotation),p=new P().crossVectors(new P(0,0,1),f).normalize(),_=new P().crossVectors(f,p).normalize(),y=Math.tan(wn.degToRad(24));let g=2;for(const m of[-e.width/2,e.width/2])for(const E of[-e.depth/2,e.depth/2])for(const w of[-e.height/2,e.height/2]){const x=new P(m,E,w).applyAxisAngle(new P(0,0,1),e.rotation);g=Math.max(g,x.dot(f)+Math.max(Math.abs(x.dot(p))/(y*Math.max(.1,q.aspect)),Math.abs(x.dot(_))/y))}q.position.copy(we.target).addScaledVector(f,g*1.12)}return q.fov=48,q.near=.03,q.far=Math.max(200,u*20),q.updateProjectionMatrix(),we.update(),!0}const t=d.data.geometry.primitives.filter(u=>u.semantic_class.startsWith("furniture_")&&d.data.hierarchy.lineage(u.owner_id).includes(d.roomId)),n=new P(t.length?t.reduce((u,f)=>u+f.center.x,0)/t.length:e.centerX,t.length?t.reduce((u,f)=>u+f.center.y,0)/t.length:e.centerY,e.elevation+Math.min(1.15,e.height*.38)),r=Math.max(.55,Math.min(1.35,Math.min(e.width,e.depth)*.14)),s=[[-e.width/2+r,-e.depth/2+r],[e.width/2-r,-e.depth/2+r],[e.width/2-r,e.depth/2-r],[-e.width/2+r,e.depth/2-r]],a=Math.cos(e.rotation),o=Math.sin(e.rotation),l=s.map(([u,f])=>new P(e.centerX+u*a-f*o,e.centerY+u*o+f*a,e.elevation+Math.max(1.65,e.height*.76))),c=u=>t.length?Math.min(...t.map(f=>Math.hypot(u.x-f.center.x,u.y-f.center.y))):u.distanceToSquared(n),h=l.reduce((u,f)=>c(f)>c(u)?f:u,l[0]);return we.target.copy(n),q.up.set(0,0,1),q.position.copy(h),q.fov=64,q.near=.03,q.far=Math.max(200,Math.max(e.width,e.depth)*20),q.updateProjectionMatrix(),we.update(),!0}async function zM(i){const e=H["paper-view-select"];if(e.hidden=!0,e.onchange=null,!!i?.paper_views)try{const t=await fetch(i.paper_views);if(!t.ok)throw new Error(`HTTP ${t.status}`);const n=await t.json();Is(e,[{value:"",label:"Saved hierarchy views…"},...n.selected_views.map(r=>({value:r.view_id,label:r.view_id}))],""),e.hidden=!1,e.onchange=async()=>{const r=n.selected_views.find(s=>s.view_id===e.value);r&&(await Ic({...r,render_profile:"interactive"}),await Lc({timeout_ms:12e4}))}}catch(t){Pt(`Saved views unavailable: ${t.message}`)}}function Vh(i={}){if(i.reset_visibility===!0&&(d.districtId="all",d.enabledSemantics=new Set(d.data.geometry.streaming?.semantics||d.data.geometry.primitives.map(s=>s.semantic_class)),ri(),Ha(!1,{focus:!1,render:!1})),d.hierarchyDisplay=hv(i.hierarchy_display,d.data.hierarchy.entities),d.presentationFocusId=i.highlight_entity_id||null,d.presentationFocusId&&!d.data.hierarchy.entities.has(d.presentationFocusId))throw new Error("Unknown presentation highlight entity");Me.localClippingEnabled=!!d.hierarchyDisplay,d.xray=!1,d.captureExposure=Number.isFinite(i.exposure)&&i.exposure>0?i.exposure:null,typeof i.daylight=="boolean"&&(d.daylight=i.daylight),["none","clear","cloudy","sunset"].includes(i.sky_preset)&&(d.skyPreset=i.sky_preset),Number.isFinite(i.sky_rotation_deg)&&(d.skyRotation=Math.max(-180,Math.min(180,i.sky_rotation_deg))),typeof i.show_grid=="boolean"&&(H["grid-toggle"].checked=i.show_grid),typeof i.show_validation=="boolean"&&(d.showValidation=i.show_validation),typeof i.show_navigation=="boolean"&&(d.showNavigation=i.show_navigation);const e=new Set(i.target_entity_ids||[]);d.observationTargetIds=e,d.observationKind=String(i.kind||"");const t=[...e].find(s=>d.data.hierarchy.entities.get(s)?.type==="floor"),n=[...e].find(s=>d.data.hierarchy.entities.get(s)?.type==="building");t&&(d.floorId=t),n&&(d.buildingId=n);const r=[...e].find(s=>d.data.hierarchy.entities.get(s)?.type==="room");if(r){if(!Za(r))throw new Error(`Observation target has no realizable room boundaries: ${r}`);d.heroRoomIds.has(r)||(d.heroRoomOnly=!1);const s=d.data.hierarchy.entities.get(r);d.roomId=r,d.floorId=s.floorId,d.buildingId=s.buildingId}if(d.hierarchyDisplay&&(d.buildingId=d.hierarchyDisplay.building_id,d.floorId=d.hierarchyDisplay.floor_id),["overview","building","floor","floor_plan","room","full"].includes(i.mode)&&(d.mode=i.mode),d.highFidelityOverview&&(d.mode="overview"),Object.prototype.hasOwnProperty.call(Eh,i.floor_camera_preset)&&(d.floorCameraPreset=i.floor_camera_preset),typeof i.auto_cutaway=="boolean"&&(d.autoCutaway=i.auto_cutaway),d.roomCameraPreset=["top","cutaway","eye"].includes(i.room_camera_preset)?i.room_camera_preset:"eye",["soft","daylight"].includes(i.room_lighting)&&(d.roomLighting=i.room_lighting),typeof i.show_outlines=="boolean"&&(d.showOutlines=i.show_outlines),typeof i.show_labels=="boolean"&&(d.showLabels=i.show_labels),typeof i.show_road_markings=="boolean"&&(d.showRoadMarkings=i.show_road_markings),typeof i.high_fidelity_overview=="boolean"&&Ha(i.high_fidelity_overview,{focus:!1,render:!1}),i.appearance&&["presentation","semantic","clay"].includes(i.appearance)&&(d.appearanceMode=i.appearance),i.render_profile&&Bt[i.render_profile]&&Nn(i.render_profile),Array.isArray(i.camera_position)&&q.position.fromArray(i.camera_position),Array.isArray(i.look_at)&&we.target.fromArray(i.look_at),Array.isArray(i.up)&&q.up.fromArray(i.up),Number.isFinite(i.fov_deg)&&(q.fov=i.fov_deg),Array.isArray(i.camera_position)){const s=q.position.distanceTo(we.target);q.near=["overview","full"].includes(d.mode)?Math.max(.03,Math.min(s/100,Math.max(.3,q.position.z)/10)):.03,q.far=Math.max(1e3,s*20),d.renderProfile==="prototype_capture"&&Number.isFinite(i.near_clip_m)&&i.near_clip_m>0&&i.near_clip_m<s*.25&&(q.near=i.near_clip_m)}q.updateProjectionMatrix(),we.update()}function Wh(){H["hero-room-toggle"].checked=d.heroRoomOnly,H["mode-buttons"].querySelectorAll("button").forEach(i=>{i.classList.toggle("active",i.dataset.mode===d.mode)}),H["appearance-select"].value=d.appearanceMode,H["room-lighting"].value=d.roomLighting,H["quality-select"].value=d.renderProfile,H["cutaway-toggle"].checked=d.autoCutaway,H["xray-toggle"].checked=d.xray,H["validation-toggle"].checked=d.showValidation,H["navigation-toggle"].checked=d.showNavigation,H["daylight-toggle"].checked=d.daylight,H["sky-select"].value=d.skyPreset,H["sky-rotation"].value=d.skyRotation,H["district-select"].value=d.districtId,H["building-select"].value=d.buildingId,$a(),H["outline-toggle"].checked=d.showOutlines,H["labels-toggle"].checked=d.showLabels,H["markings-toggle"].checked=d.showRoadMarkings,H["high-fidelity-toggle"].checked=d.highFidelityOverview,H["camera-high-fidelity"].classList.toggle("active",d.highFidelityOverview),ii()}function Ur(){const i=d.mode==="room"?[d.roomId]:["floor","floor_plan"].includes(d.mode)?[d.buildingId,d.floorId]:d.mode==="building"?[d.buildingId]:[];return JSON.stringify({geometryRevision:d.geometryRevision,mode:d.mode,selection:i,district:d.districtId,appearance:d.appearanceMode,profile:d.renderProfile,daylight:d.daylight,skyPreset:d.skyPreset,skyRotation:d.skyRotation,cutaway:d.autoCutaway,roomCamera:d.roomCameraPreset,roomLighting:d.roomLighting,outlines:d.showOutlines,labels:d.showLabels,markings:d.showRoadMarkings,xray:d.xray,hierarchyDisplay:d.hierarchyDisplay,presentationFocusId:d.presentationFocusId,exposure:d.captureExposure,navigation:d.showNavigation,validation:d.showValidation,heroRoomOnly:d.heroRoomOnly,observationTargets:[...d.observationTargetIds].sort(),observationKind:d.observationKind,highFidelityOverview:d.highFidelityOverview,semantics:[...d.enabledSemantics].sort()})}function Xh(){const i=JSON.parse(Ur());return d.renderProfile==="navigation"&&delete i.profile,fn(d.renderProfile)&&(q.updateMatrixWorld(),i.screen=[ka||H.viewport.clientHeight*Me.getPixelRatio(),...q.matrixWorld.elements,...q.projectionMatrix.elements].map(e=>Math.round(e*1e4)/1e4)),JSON.stringify(i)}async function Ic(i){if(!d.data)throw new Error("CityG scene is not loaded yet");Vh(i),!Array.isArray(i.camera_position)&&d.mode==="room"&&Qa(),!Array.isArray(i.camera_position)&&["floor","floor_plan"].includes(d.mode)&&Pc(d.mode==="floor_plan"?"top":d.floorCameraPreset),Wh();const t=Ur()!==d.geometryRenderSignature;return t||fn(d.renderProfile)?$e():d.renderProfile!=="paper_capture"&&Me.render(Ae,q),await Ya(),{view_id:i.view_id||null,ready:!d.streaming||d.streaming.status.ready,floor_camera_preset:d.floorCameraPreset,room_camera_preset:d.roomCameraPreset,geometry_rebuilt:t,geometry_rebuild_count:d.geometryRebuildCount,render_profile:d.renderProfile,high_fidelity_overview:d.highFidelityOverview,visible_primitive_count:d.visiblePrimitives.length,selected_entities:{building_id:d.buildingId,floor_id:d.floorId,room_id:d.roomId},hierarchy_display:d.hierarchyDisplay,camera:{camera_position:q.position.toArray(),look_at:we.target.toArray(),up:q.up.toArray(),fov_deg:q.fov,near_clip_m:q.near},shell_building_ids:[...new Set(d.visiblePrimitives.filter(n=>d.data.layerMap.get(n.layer_id)?.layer_type==="building_shell").map(n=>d.data.hierarchy.entities.get(n.owner_id)?.buildingId).filter(Boolean))].sort(),transparent_building_ids:[...new Set(d.visiblePrimitives.filter(Ia).map(n=>d.data.hierarchy.entities.get(n.owner_id)?.buildingId))],interior_floor_ids:[...new Set(d.visiblePrimitives.filter(n=>d.data.layerMap.get(n.layer_id)?.layer_type==="floor").map(n=>d.data.hierarchy.entities.get(n.owner_id)?.floorId).filter(Boolean))].sort(),asset_status:{...d.assetLoadState}}}function gi(){const i=d.streaming?.status||{ready:!0,pending:0,failed:0,generation:0},e=d.renderProfile==="navigation"?{...d.assetLoadState,generation:d.assetRenderGeneration,ready:!0,pending:0,failed:0}:d.assetLoadState,t=d.renderProfile==="navigation"?[]:[...d.materialTextureUrls].map(l=>xc.get(l)),n=t.filter(l=>l==="pending").length,r=t.filter(l=>l==="failed").length,s=Bt[d.renderProfile].environment&&!!Ms(d.data?.raw.config).filename,a=s&&dn!=="ready"&&dn!=="failed"?1:0,o=s&&dn==="failed"?1:0;return{...e,ready:!d.contextLost&&e.ready&&i.ready&&n===0&&r===0&&!a&&!o,gpu:{context_lost:d.contextLost,context_losses:d.contextLosses,geometries:Me.info.memory.geometries,textures:Me.info.memory.textures,draw_calls:Me.info.render.calls,triangles:Me.info.render.triangles,...kr.stats()},pending:e.pending+n+i.pending+a,failed:e.failed+r+i.failed+o,environment_state:s?dn:"not_requested",sky:{selected:d.skyPreset,active:!!(Ms(d.data?.raw.config).preset&&Ae.background?.isTexture),rotation_deg:d.skyRotation,sun_direction:et.position.clone().sub(et.target.position).normalize().toArray()},screen_lod:{...rs},shading:{shadows:Me.shadowMap.enabled,environment:!!Ae.environment,physical_glass:Bt[d.renderProfile].physicalGlass,textures:Bt[d.renderProfile].materialTextures},geometry_streaming:{...i,city_lod:!!d.streaming,total_primitives:d.data?.geometry.streaming?.total_primitives||d.data?.geometry.primitives.length||0,resident_primitives:d.data?.geometry.primitives.length||0},material_textures_expected:t.length,material_textures_pending:n,material_textures_failed:r,render_profile:d.renderProfile,geometry_rebuild_count:d.geometryRebuildCount,capture_sampling:d.renderProfile==="prototype_capture"?{outdoor_asset_budget:64,selected:d.prototypeCaptureAssetIds.size,original_scene_unchanged:!0}:null,visible_primitive_count:d.visiblePrimitives.length}}async function Lc(i={}){const e=Math.max(100,Number(i.timeout_ms??6e4)),t=Math.max(0,Number(i.quiet_ms??160)),n=performance.now()+e;for(;performance.now()<n;){const r=d.assetRenderGeneration,s=d.assetReadyPromise,a=[...d.materialTextureUrls].map(c=>bh.get(c)),o=Math.max(1,n-performance.now());await Promise.race([Promise.allSettled([s,d.streaming?.promise,Ca,...a]),new Promise(c=>setTimeout(c,Math.min(500,o)))]);const l=gi();if(l.generation===r&&l.pending===0&&l.failed>0)return{...l,ready:!1,timed_out:!1};if(l.generation===r&&l.ready&&l.pending===0){t&&await new Promise(h=>setTimeout(h,t));const c=gi();if(c.generation===r&&c.ready&&c.pending===0)return{...c,timed_out:!1}}await new Promise(c=>setTimeout(c,Math.min(16,Math.max(1,n-performance.now()))))}return{...gi(),ready:!1,timed_out:!0}}function kM(){if(d.contextLost)throw new Error("Graphics context is lost; wait for recovery before capturing");return Dh(),(d.cameraDirty||["paper_capture","prototype_capture"].includes(d.renderProfile))&&(Me.render(Ae,q),d.cameraDirty=!1),Me.domElement.toDataURL("image/png")}async function jh({longEdge:i=2560,download:e=!0,timeoutMs:t=12e4}={}){if(!d.data||!window.citygObservation.ready)throw new Error("Wait for the scene to finish loading");if(mi)throw new Error("An image export is already in progress");if(zi?.status().playing)throw new Error("Pause the robot replay before saving an image");const n={profile:d.renderProfile,camera:q.clone(),target:we.target.clone(),enabled:we.enabled,damping:we.enableDamping},r=yv(H.viewport.clientWidth,H.viewport.clientHeight,i,Math.min(Me.capabilities.maxTextureSize,Me.getContext().getParameter(Me.getContext().MAX_RENDERBUFFER_SIZE))),s=performance.now(),a=[...document.querySelectorAll(".topbar, .panel, #viewport")].map(l=>[l,l.inert]);let o;mi=!0,ka=r.height,d.navigationKeys.clear(),clearTimeout(d.streamCameraTimer),we.enabled=!1,a.forEach(([l])=>{l.inert=!0}),H["hq-screenshot-button"].disabled=!0;try{Zn(!0,"HQ PNG: preparing models and textures…"),await new Promise(_=>requestAnimationFrame(()=>requestAnimationFrame(_))),Nn("snapshot"),$e(),o=setInterval(()=>{const _=gi();Zn(!0,`HQ PNG: loading models/textures (${_.pending} pending)…`)},300);const l=await Lc({timeout_ms:t,quiet_ms:180});if(clearInterval(o),!l.ready||l.failed||l.fallback)throw new Error(l.timed_out?"HQ export timed out loading assets; try again after loading, or use a smaller scene scope":"HQ export stopped: some assets or textures failed to load (no incomplete image saved)");const c=performance.now();Zn(!0,`HQ PNG: rendering ${r.width} × ${r.height}…`),await new Promise(_=>requestAnimationFrame(()=>requestAnimationFrame(_))),Me.setDrawingBufferSize(r.width,r.height,1),Me.render(Ae,q);const h={...Me.info.render},u=await xv(Me.domElement),f=`${d.data.city.id}_${d.mode}_${new Date().toISOString().replace(/[:.]/g,"-")}_HQ.png`;if(e){const _=URL.createObjectURL(u),y=document.createElement("a");y.download=f,y.href=_,document.body.appendChild(y),y.click(),y.remove(),setTimeout(()=>URL.revokeObjectURL(_),3e4)}const p={filename:f,...r,bytes:u.size,prepare_ms:Math.round(c-s),render_encode_ms:Math.round(performance.now()-c),assets:l,draw:h,camera_position:q.position.toArray(),look_at:we.target.toArray(),city_lod:!!d.streaming};return window.citygObservation.lastSnapshot=p,Pt(`HQ PNG ${r.width} × ${r.height}${e?" sent to browser downloads":" rendered"}`),p}finally{clearInterval(o);try{ka=null,q.copy(n.camera),we.target.copy(n.target),Nn(n.profile),Me.setSize(H.viewport.clientWidth,H.viewport.clientHeight,!1),$e()}finally{mi=!1,we.enabled=n.enabled,we.enableDamping=n.damping,a.forEach(([l,c])=>{l.inert=c}),H["hq-screenshot-button"].disabled=!1,Zn(!1),vc(),d.cameraDirty=!0}}}function qh({download:i=!0}={}){if(!d.data)throw new Error("Load a scene before exporting a render view");if(mi)throw new Error("Wait for the current image export to finish");const e=zi?.status()||null;if(e?.playing)throw new Error("Pause robot playback before exporting the render view");const t=d.data.raw.config||{},n=vv({camera:q,target:we.target,viewport:{width:H.viewport.clientWidth,height:H.viewport.clientHeight,bufferWidth:Me.domElement.width,bufferHeight:Me.domElement.height},sceneRef:{city_id:d.data.city.id,label:t.label||"",source:t.source||"",original_source:t.original_source||null,geometry_revision:d.geometryRevision,total_primitives:d.data.geometry.streaming?.total_primitives||d.data.geometry.primitives.length},selection:{district_id:d.districtId,building_id:d.buildingId||null,floor_id:d.floorId||null,room_id:d.roomId||null,primitive_id:d.selectedPrimitive?.id||null},visibility:{mode:d.mode,room_camera_preset:d.roomCameraPreset,floor_camera_preset:d.floorCameraPreset,auto_cutaway:d.autoCutaway,xray_shells:d.xray,hierarchy_display:d.hierarchyDisplay,presentation_focus_id:d.presentationFocusId,hero_room_only:d.heroRoomOnly,enabled_semantics:[...d.enabledSemantics].sort(),show_grid:Dr.visible,show_outlines:d.showOutlines,show_labels:d.showLabels,show_road_markings:d.showRoadMarkings,show_navigation:d.showNavigation,show_validation:d.showValidation,door_states:Object.fromEntries(d.doorStates),visible_primitive_count:d.visiblePrimitives.length},lighting:{render_profile:d.renderProfile,appearance:d.appearanceMode,room_lighting:d.roomLighting,daylight:d.daylight,sky_preset:d.skyPreset,sky_rotation_deg:d.skyRotation,tone_mapping:"ACESFilmic",tone_mapping_exposure:Me.toneMappingExposure,environment_intensity:Ae.environmentIntensity,shadows:Me.shadowMap.enabled},replay:e,assetStatus:gi()});if(i){const r=URL.createObjectURL(new Blob([JSON.stringify(n,null,2)+`
`],{type:"application/json"})),s=document.createElement("a");s.download=Mv(n),s.href=r,document.body.appendChild(s),s.click(),s.remove(),setTimeout(()=>URL.revokeObjectURL(r),3e4),Pt("Render view JSON sent to browser downloads")}return n}window.citygObservation={ready:!1,setView:Ic,getAssetStatus:gi,waitForAssets:Lc,captureFrame:kM,saveHighQualityImage:jh,exportRenderView:qh,getViewState:()=>({camera_position:q.position.toArray(),look_at:we.target.toArray(),up:q.up.toArray(),fov_deg:q.fov,aspect:q.aspect,mode:d.mode,near_clip_m:q.near,far_clip_m:q.far,render_profile:d.renderProfile,appearance:d.appearanceMode,sky_preset:d.skyPreset,sky_rotation_deg:d.skyRotation,daylight:d.daylight})};function Us(){if(d.selectedPrimitive)return kh(d.selectedPrimitive);if(d.mode==="floor_plan"){Hh();return}if(!(d.mode==="room"&&d.roomId&&Qa())&&!(d.mode==="floor"&&d.floorId&&Pc(d.floorCameraPreset))&&!((d.mode==="building"||d.mode==="floor")&&d.buildingId&&UM(Tc().get(d.buildingId)))){if(d.districtId!=="all")return zh(d.districtId);Fi("iso")}}function ri(){d.cameraDirty=!0,d.selectedPrimitive=null,nn.visible=!1,Wt(Ui),Nr()}function Yh(){const i=[...d.enabledSemantics].sort();H.legend.replaceChildren(...i.map(e=>{const t=document.createElement("span"),n=document.createElement("i");return n.className="swatch",n.style.background=`#${(Pr[e]||9085852).toString(16).padStart(6,"0")}`,t.append(n,document.createTextNode(e.replaceAll("_"," "))),t})),H.legend.style.display=d.appearanceMode==="semantic"?"flex":"none"}function Zn(i,e="Preparing city geometry"){H.loading.classList.toggle("hidden",!i),H.loading.querySelector("span").textContent=e}function Pt(i){H.toast.textContent=i,H.toast.classList.add("show"),clearTimeout(xu),xu=setTimeout(()=>H.toast.classList.remove("show"),2400)}function lr(i){return Number(i).toFixed(Math.abs(i)>=100?1:2)}function HM(i){return i instanceof HTMLInputElement||i instanceof HTMLSelectElement||i instanceof HTMLTextAreaElement||i?.isContentEditable}const GM=new Set(["w","a","s","d","q","e","arrowleft","arrowright","arrowup","arrowdown","shift"]);H.viewport.addEventListener("pointerenter",()=>{d.keyboardNavigationActive=!0});H.viewport.addEventListener("pointerleave",()=>{d.keyboardNavigationActive=!1,d.navigationKeys.clear()});window.addEventListener("keydown",i=>{if(mi||!d.keyboardNavigationActive||HM(i.target))return;const e=i.key.toLowerCase();GM.has(e)&&(d.navigationKeys.add(e),i.preventDefault())});window.addEventListener("keyup",i=>{d.navigationKeys.delete(i.key.toLowerCase())});window.addEventListener("blur",()=>d.navigationKeys.clear());Me.domElement.addEventListener("pointerdown",i=>{hr=[i.clientX,i.clientY],d.cameraInteracting=!0});Me.domElement.addEventListener("pointerup",i=>{const e=hr&&Math.hypot(i.clientX-hr[0],i.clientY-hr[1])<=4;if(d.cameraInteracting=!1,hr=null,d.renderProfile==="navigation"&&(Me.render(Ae,q),d.lastNavigationRenderTime=performance.now()),!e)return;const t=Me.domElement.getBoundingClientRect();Xo.x=(i.clientX-t.left)/t.width*2-1,Xo.y=-((i.clientY-t.top)/t.height)*2+1,yu.setFromCamera(Xo,q);const n=yu.intersectObjects([...Li.children,...Qn.children,...Mn.children],!0)[0];if(!n){d.selectedPrimitive=null,Nr(),nn.visible=!1;return}if(n.instanceId!==void 0){Gl(n.object.userData.entries[n.instanceId]);return}let r=n.object;for(;r&&!r.userData.entry;)r=r.parent;r?.userData.entry?Gl(r.userData.entry):(d.selectedPrimitive=null,Nr(),nn.visible=!1)});Me.domElement.addEventListener("pointercancel",()=>{hr=null,d.cameraInteracting=!1,d.renderProfile==="navigation"&&Me.render(Ae,q)});H["mode-buttons"].addEventListener("click",i=>{const e=i.target.closest("button[data-mode]");e&&(d.mode=e.dataset.mode,d.hierarchyDisplay=null,d.presentationFocusId=null,d.mode==="floor"&&(d.floorCameraPreset="perspective"),d.mode!=="floor"&&d.mode!=="floor_plan"&&(d.floorCameraPreset="perspective"),H["mode-buttons"].querySelectorAll("button").forEach(t=>t.classList.toggle("active",t===e)),ii(),ri(),$e(),["building","floor","floor_plan","room"].includes(d.mode)&&Us())});H["district-select"].addEventListener("change",i=>{d.districtId=i.target.value,ri(),bc(),$e()});H["building-select"].addEventListener("change",i=>{d.hierarchyDisplay=null,d.presentationFocusId=null,d.buildingId=i.target.value,ri(),$a(),$e(),Ka(),["building","floor","floor_plan","room"].includes(d.mode)&&Us()});H["floor-select"].addEventListener("change",i=>{d.hierarchyDisplay=null,d.presentationFocusId=null,d.floorId=i.target.value,d.roomId="",Ls(),ri(),$e(),Ka(),["floor","floor_plan","room"].includes(d.mode)&&Us()});H["room-select"].addEventListener("change",i=>{d.roomId=i.target.value,ri(),$e(),d.mode==="room"&&Us()});H["hero-room-toggle"].addEventListener("change",i=>{d.heroRoomOnly=i.target.checked,d.roomId="",Ls(),ri(),$e()});H["focus-button"].addEventListener("click",Us);H["floor-plan-button"].addEventListener("click",()=>{d.hierarchyDisplay=null,d.presentationFocusId=null,Gh("top")});H["floor-camera-buttons"]?.addEventListener("click",i=>{const e=i.target.closest("button[data-floor-camera]");e&&Gh(e.dataset.floorCamera)});H["room-view-button"].addEventListener("click",()=>{if(d.hierarchyDisplay=null,d.presentationFocusId=null,!d.buildingId||!d.floorId||!d.roomId){Pt("Select a building, floor, and room first");return}if(!Za(d.roomId)){Pt("This planned room is outside the realized building massing");return}d.mode="room",H["mode-buttons"].querySelectorAll("button").forEach(i=>{i.classList.toggle("active",i.dataset.mode===d.mode)}),ri(),ii(),$e(),Qa()});H["room-camera-buttons"].addEventListener("click",i=>{const e=i.target.closest("button[data-room-camera]");!e||!d.roomId||(d.roomCameraPreset=e.dataset.roomCamera,Qa(),Ka(),$e())});H["room-lighting"].addEventListener("change",i=>{d.roomLighting=i.target.value,$e()});H["appearance-select"].addEventListener("change",i=>{d.appearanceMode=i.target.value,Yh(),$e()});let Vl=0;H["quality-select"].addEventListener("change",async i=>{const e=i.target.value,t=++Vl;if(!d.contextLost&&(H["render-status"].textContent=e==="navigation"?"Releasing high-quality resources…":"Preparing Presentation · loading models in batches…",await new Promise(n=>requestAnimationFrame(()=>requestAnimationFrame(n))),!(t!==Vl||d.contextLost)))try{Nn(e,{persist:!0}),$e(),ii()}catch(n){Nn("navigation"),$e(),Hr(n)}});const Ii=document.createElement("div");Ii.id="gpu-recovery-notice";Ii.style.cssText="display:none;position:absolute;top:16px;left:16px;right:16px;z-index:30;padding:16px;background:#21333a;color:white;border:1px solid #e4ac63;border-radius:8px";H.viewport.append(Ii);function Kh(i){Ii.replaceChildren(document.createTextNode(i+" "));const e=document.createElement("button");e.textContent="Dismiss",e.onclick=()=>{Ii.style.display="none"};const t=document.createElement("button");t.textContent="Reload Viewer",t.onclick=()=>window.location.reload(),Ii.append(e,t),Ii.style.display="block"}Me.domElement.addEventListener("webglcontextlost",i=>{i.preventDefault(),d.contextLost=!0,d.contextLosses++,Vl++,clearTimeout(d.streamCameraTimer),Bh(),kr.clear(),Wt(Mn);const e=new Set([Zt,Ja,wc,...Aa.values()]),t=new Set;Ae.traverse(n=>{n.geometry&&e.add(n.geometry);for(const r of[n.material].flat().filter(Boolean))t.add(r)}),e.forEach(n=>n.dispose()),t.forEach(n=>n.dispose()),yc.forEach(n=>n.dispose()),Pa++;for(const n of Mr.values())n.target.dispose(),n.source.dispose();Mr.clear(),os.clear(),vr=null,ds?.dispose(),ds=null,as="",dn="idle",Ae.environment=null,et.shadow.map?.dispose(),et.shadow.map=null,vs.dispose(),Zn(!1),Kh("Graphics context lost. Waiting for the browser to restore it; your scene and camera are unchanged. If it does not recover, reload this Viewer.")});Me.domElement.addEventListener("webglcontextrestored",()=>{vs=new Ba(Me),d.contextLost=!1,Nn("navigation",{persist:!0}),d.navigationGeometryContentSignature="",$e(),Kh("Graphics restored in Navigation preview. Your camera is preserved. You can retry Presentation, or move closer to a smaller area first.")});H["daylight-toggle"].addEventListener("change",i=>{d.daylight=i.target.checked,Ps(),$e()});H["sky-select"].addEventListener("change",i=>{d.skyPreset=i.target.value,$e()});H["sky-rotation"].addEventListener("change",i=>{d.skyRotation=Number(i.target.value),$e()});H["cutaway-toggle"].addEventListener("change",i=>{d.autoCutaway=i.target.checked,$e()});H["outline-toggle"].addEventListener("change",i=>{d.showOutlines=i.target.checked,$e()});H["labels-toggle"].addEventListener("change",i=>{d.showLabels=i.target.checked,$e()});H["markings-toggle"].addEventListener("change",i=>{d.showRoadMarkings=i.target.checked,$e()});H["high-fidelity-toggle"].addEventListener("change",i=>{Ha(i.target.checked)});H["xray-toggle"].addEventListener("change",i=>{d.xray=i.target.checked,$e()});H["hierarchy-display-button"].addEventListener("click",async()=>{if(!d.buildingId||!d.floorId)return Pt("Select a building and floor first");const i=d.data.hierarchy.entities.get(d.floorId)?.entity;await Ic({mode:"overview",kind:"hierarchy",auto_cutaway:!1,target_entity_ids:[d.buildingId,d.floorId],hierarchy_display:{building_id:d.buildingId,floor_id:d.floorId,shell_opacity:.12,cut_above_m:i.elevation_m+i.height_m}}),Pt("Only the selected shell is translucent. Scene mode exits hierarchy display.")});H["navigation-toggle"].addEventListener("change",i=>{d.showNavigation=i.target.checked,$e()});H["validation-toggle"].addEventListener("change",i=>{d.showValidation=i.target.checked,$e()});H["grid-toggle"].addEventListener("change",i=>{Dr.visible=i.target.checked,d.cameraDirty=!0});H["door-button"].addEventListener("click",()=>{const i=d.selectedPrimitive?.metadata?.state_machine_id;if(!i)return;const e=d.data.interactions.state_machines.find(t=>t.id===i);if(e?.state_type==="elevator_controller"){const t=Object.keys(e.states).sort((r,s)=>e.states[r].current_level-e.states[s].current_level),n=t.indexOf(d.doorStates.get(i));d.doorStates.set(i,t[(n+1)%t.length])}else d.doorStates.set(i,d.doorStates.get(i)==="open"?"closed":"open");$e(),Nr()});H["route-button"].addEventListener("click",LM);H["camera-iso"].addEventListener("click",()=>Fi("iso"));H["camera-high-fidelity"].addEventListener("click",()=>{Ha(!d.highFidelityOverview)});H["camera-top"].addEventListener("click",()=>Fi("top"));H["camera-street"].addEventListener("click",BM);H["camera-reset"].addEventListener("click",()=>Fi("fit"));H["reload-button"].addEventListener("click",()=>Rh().catch(Hr));H["folder-input"].addEventListener("change",i=>lM(i.target.files).catch(Hr));H["screenshot-button"].addEventListener("click",()=>{Me.render(Ae,q);const i=document.createElement("a");i.download=`${d.data?.city?.id||"cityg"}.png`,i.href=Me.domElement.toDataURL("image/png"),i.click()});H["hq-screenshot-button"].addEventListener("click",()=>jh().catch(Hr));H["export-render-view-button"].addEventListener("click",()=>{try{qh()}catch(i){Hr(i)}});function Hr(i){console.error(i),Zn(!1),Pt(i.message||String(i))}zi=gv({scene:Ae,cameraState:()=>({position:q.position.toArray(),target:we.target.toArray(),up:q.up.toArray()}),begin:()=>{d.renderProfile==="navigation"&&Nn("review")},rebuild:()=>{d.geometryRevision+=1,d.geometryRenderSignature="",$e()},draw:()=>{Me.render(Ae,q),d.cameraDirty=!0},error:Pt,follow:(i,e,t={})=>{const r=d.data.city.districts.flatMap(l=>l.parcels.flatMap(c=>c.buildings)).find(l=>i[0]>=l.footprint.min_x&&i[0]<=l.footprint.max_x&&i[1]>=l.footprint.min_y&&i[1]<=l.footprint.max_y),s=r?.floors.reduce((l,c)=>Math.abs(c.elevation_m-(i[2]-.75))<Math.abs(l.elevation_m-(i[2]-.75))?c:l,r.floors[0]),a=s?.id||"outdoors";a!==e&&(d.mode=r?"floor_plan":"overview",d.buildingId=r?.id||"",d.floorId=s?.id||"",d.autoCutaway=!0,d.geometryRenderSignature="",bc(),$a(),Ls(),ii(),H["mode-buttons"].querySelectorAll("button").forEach(l=>{l.classList.toggle("active",l.dataset.mode===(r?"floor":"overview"))}),$e());const o=_v(i,t.yaw,t.mode,!!r);return q.up.set(0,0,1),q.position.fromArray(o.position),we.target.fromArray(o.target),we.update(),a}});Rh().catch(Hr);
