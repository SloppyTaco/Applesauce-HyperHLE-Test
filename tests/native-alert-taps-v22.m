/* Public fixture: actual external XCTest taps while a main GCD block owns
 * the app, using the exact default/tracking run-loop turns in SDL's pump.
 * No game data, synthetic selection, private API or UIAlertController edits.
 */
#import <UIKit/UIKit.h>
#import <CoreFoundation/CoreFoundation.h>
#include <stdio.h>
#include <unistd.h>
#if defined(TOUCHHLE_ALERT_BASELINE)
#include "../patches/async-alert-uikit-v20.inc"
#else
#include "../patches/async-alert-uikit-v22.inc"
#endif

static void record(NSString *line)
{
    NSString *path = [NSHomeDirectory() stringByAppendingPathComponent:@"Documents/native-taps-v22.log"];
    FILE *file = fopen(path.fileSystemRepresentation, "a");
    if (file) { fprintf(file, "%s\n", line.UTF8String); fclose(file); }
    NSLog(@"%@", line);
}

@interface TouchHLETapScene : UIResponder <UIWindowSceneDelegate>
@property(nonatomic, strong) UIWindow *window;
@property(nonatomic, strong) UILabel *status;
@property(nonatomic, strong) UIButton *gameButton;
@property(nonatomic) unsigned gameTouches;
@property(nonatomic) unsigned heartbeats;
@end
@implementation TouchHLETapScene
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)session
    options:(UISceneConnectionOptions *)options
{
    (void)session; (void)options;
    NSString *logPath = [NSHomeDirectory() stringByAppendingPathComponent:@"Documents/native-taps-v22.log"];
    [[NSFileManager defaultManager] removeItemAtPath:logPath error:nil];
    self.window = [[UIWindow alloc] initWithWindowScene:(UIWindowScene *)scene];
    UIViewController *root = [UIViewController new];
    root.view.backgroundColor = UIColor.systemBackgroundColor;
    self.status = [[UILabel alloc] initWithFrame:CGRectMake(20, 100, 350, 60)];
    self.status.text = @"Preparing native tap test";
    self.status.accessibilityIdentifier = @"fixture.status";
    [root.view addSubview:self.status];
    self.gameButton = [UIButton buttonWithType:UIButtonTypeSystem];
    self.gameButton.frame = CGRectMake(40, 200, 250, 60);
    [self.gameButton setTitle:@"Game touch" forState:UIControlStateNormal];
    [self.gameButton addTarget:self action:@selector(gameTapped:) forControlEvents:UIControlEventTouchUpInside];
    [root.view addSubview:self.gameButton];
    self.window.rootViewController = root;
    [self.window makeKeyAndVisible];
    // The real host invokes the core from main.asyncAfter. A timer-only
    // fixture would allow main-queue handlers to run and miss this failure.
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, NSEC_PER_SEC), dispatch_get_main_queue(), ^{
        [self occupiedMainQueueTest];
    });
}
- (void)gameTapped:(UIButton *)sender
{
    (void)sender;
    self.gameTouches++;
    record([NSString stringWithFormat:@"[NATIVE TAP v22] Game touch %u delivered", self.gameTouches]);
}
- (void)occupiedMainQueueTest
{
    record(@"[NATIVE TAP v22] START occupied main GCD block; real SDL default/tracking turns");
    __weak TouchHLETapScene *weakSelf = self;
    NSTimer *heartbeat = [NSTimer scheduledTimerWithTimeInterval:0.01 repeats:YES block:^(NSTimer *timer) {
        (void)timer; weakSelf.heartbeats++;
    }];
    char title[] = "Download test";
    char no[] = "Cancel";
    char yes[] = "Download";
    const char *buttons[] = {no, yes};
    uint64_t token = TouchHLE_BeginAsyncAlertV20(self.window, title, "External tap required", buttons, 2);
    unsigned phase = 0;
    BOOL pass = NO;
    CFAbsoluteTime start = CFAbsoluteTimeGetCurrent();
    while (CFAbsoluteTimeGetCurrent() - start < 90) {
        @autoreleasepool {
            SInt32 result;
            do { result = CFRunLoopRunInMode(kCFRunLoopDefaultMode, 0.000002, TRUE); }
            while (result == kCFRunLoopRunHandledSource);
            do { result = CFRunLoopRunInMode((CFStringRef)UITrackingRunLoopMode, 0.000002, TRUE); }
            while (result == kCFRunLoopRunHandledSource);
            int selected = token ? TouchHLE_PollAsyncAlertV20(token) : -1;
            if (selected >= 0) {
#if defined(TOUCHHLE_ALERT_BASELINE)
                record(@"[NATIVE TAP v22] BASELINE handler delivered; failure not reproduced");
                self.status.text = @"Baseline not reproduced";
                break;
#else
                int wanted = phase == 0 ? 1 : 0;
                if (selected != wanted || TouchHLE_PollAsyncAlertV20(token) != -2 || !self.window.isKeyWindow) {
                    record(@"[NATIVE TAP v22] FAIL wrong/duplicate selected index or key window");
                    break;
                }
                token = 0;
                self.status.text = phase == 0 ? @"Download delivered" : @"Cancel delivered";
                record([NSString stringWithFormat:@"[NATIVE TAP v22] PASS actual button index %d delivered exactly once", selected]);
                phase++;
#endif
            }
#if defined(TOUCHHLE_ALERT_BASELINE)
            // The external test observes disappearance after tapping Download.
            // Pending through 25 seconds demonstrates the native handler gap;
            // after releasing the GCD block any late handler is stale/ignored.
            if (CFAbsoluteTimeGetCurrent() - start > 25) {
                record(@"[NATIVE TAP v22] BASELINE pending after external tap; heartbeats continue");
                self.status.text = @"Baseline pending";
                break;
            }
#else
            if (phase == 1 && self.gameTouches == 1) {
                token = TouchHLE_BeginAsyncAlertV20(self.window, "Cancel test", "External tap required", buttons, 2);
                phase = 2;
            }
            if (phase == 3 && self.gameTouches == 2 && self.heartbeats >= 2) {
                pass = YES;
                self.status.text = @"All native taps passed";
                record(@"[NATIVE TAP v22] ALL PASS 4 actual taps: Download, game, Cancel, game");
                break;
            }
#endif
            usleep(1000);
        }
    }
    [heartbeat invalidate];
    TouchHLE_ResetAsyncAlertsV20();
#if !defined(TOUCHHLE_ALERT_BASELINE)
    if (!pass) { self.status.text = @"Native tap failure"; record(@"[NATIVE TAP v22] FAIL timed out or invalid selection"); }
#else
    (void)pass;
#endif
}
@end

@interface TouchHLETapApp : UIResponder <UIApplicationDelegate>
@end
@implementation TouchHLETapApp
- (UISceneConfiguration *)application:(UIApplication *)application
    configurationForConnectingSceneSession:(UISceneSession *)session options:(UISceneConnectionOptions *)options
{
    (void)application; (void)options;
    UISceneConfiguration *config = [[UISceneConfiguration alloc] initWithName:@"Tap" sessionRole:session.role];
    config.delegateClass = [TouchHLETapScene class];
    return config;
}
@end
int main(int argc, char **argv)
{
    @autoreleasepool { return UIApplicationMain(argc, argv, nil, NSStringFromClass([TouchHLETapApp class])); }
}
