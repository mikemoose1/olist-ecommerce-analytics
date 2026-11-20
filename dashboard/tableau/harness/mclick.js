ObjC.import('CoreGraphics');
function run(argv){
  var x=parseFloat(argv[0]), y=parseFloat(argv[1]);
  var p=$.CGPointMake(x,y);
  var mv=$.CGEventCreateMouseEvent($(),$.kCGEventMouseMoved,p,$.kCGMouseButtonLeft); $.CGEventPost($.kCGHIDEventTap,mv);
  delay(0.3);
  var d=$.CGEventCreateMouseEvent($(),$.kCGEventLeftMouseDown,p,$.kCGMouseButtonLeft); $.CGEventPost($.kCGHIDEventTap,d);
  delay(0.1);
  var u=$.CGEventCreateMouseEvent($(),$.kCGEventLeftMouseUp,p,$.kCGMouseButtonLeft); $.CGEventPost($.kCGHIDEventTap,u);
  return 'posted '+x+','+y;
}
